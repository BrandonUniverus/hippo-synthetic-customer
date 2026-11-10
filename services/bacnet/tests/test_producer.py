import copy
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from services.bacnet.producer import CONFIG, build_values, scenarios, window_start
from services.sources.generation import create_model


class ThermalModel:
    accounts = {
        'a': {'id': 'ntp_one', 'meters': [{'id': 'steam_one', 'channels': [{'unit': 'klb'}]}]},
        'b': {'id': 'ntp_two', 'meters': [{'id': 'steam_two', 'channels': [{'unit': 'klb'}]}]},
        'other': {'id': 'unrelated', 'meters': [{'id': 'wrong', 'channels': [{'unit': 'klb'}]}]},
    }

    def __init__(self):
        self.reads = []

    def meter_value(self, meter, quantity, end, minutes):
        self.reads.append((meter, quantity, end, minutes))
        return {'ntp_science_center_chilled_water': Decimal('95'),
                'ntp_recreation_center_chilled_water': Decimal('95'),
                'steam_one': Decimal('23'), 'steam_two': Decimal('23')}[meter]


class HourlyThermalModel(ThermalModel):
    """Values that change every hour, so a held value is distinguishable from the current one."""

    def meter_value(self, meter, quantity, end, minutes):
        self.reads.append((meter, quantity, end, minutes))
        return Decimal(90 + end.hour)


def utc(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc)


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text())

    def test_override_window_holds_the_value_from_when_it_opened(self):
        # Tuesday 03:20 Pacific: the hour 02:00-03:00 lies inside the 02:00-04:00 chiller override.
        values = build_values(HourlyThermalModel(), self.config, utc('2026-11-10T03:20:00-08:00'))
        science = values['science_chw_tons']
        self.assertEqual('2026-11-10T11:00:00+00:00', science['intervalEndUtc'])
        self.assertEqual(90 + 10, science['value'])  # the hour that ended at 02:00 Pacific, 10:00 UTC
        self.assertTrue(science['status']['overridden'])
        self.assertEqual('science-chiller-override', science['status']['scenario'])
        self.assertFalse(science['status']['inAlarm'])
        self.assertFalse(science['status']['fault'])
        recreation = values['recreation_chw_tons']
        self.assertEqual(90 + 11, recreation['value'])
        self.assertFalse(recreation['status']['overridden'])
        self.assertNotIn('scenario', recreation['status'])

    def test_windows_keep_campus_clock_time_across_daylight_saving(self):
        override = next(s for s in scenarios(self.config) if s['key'] == 'science-chiller-override')
        self.assertEqual(utc('2026-07-07T02:00:00-07:00'), window_start(override, utc('2026-07-07T03:00:00-07:00'), 60))
        self.assertEqual(utc('2026-11-10T02:00:00-08:00'), window_start(override, utc('2026-11-10T04:00:00-08:00'), 60))
        self.assertIsNone(window_start(override, utc('2026-11-10T05:00:00-08:00'), 60))  # 04:00-05:00 is after the window
        self.assertIsNone(window_start(override, utc('2026-11-11T03:00:00-08:00'), 60))  # a Wednesday

    def test_out_of_service_and_fault_set_the_bacnet_flags(self):
        swap = build_values(HourlyThermalModel(), self.config, utc('2026-11-11T11:05:00-08:00'))['recreation_chw_ton_hours']
        self.assertTrue(swap['status']['outOfService'])
        self.assertFalse(swap['status']['inAlarm'])
        self.assertEqual('no-fault-detected', swap['status']['reliability'])
        fault = build_values(HourlyThermalModel(), self.config, utc('2026-12-01T06:20:00-08:00'))['plant_steam_header_psig']
        self.assertEqual('2026-12-01T14:15:00+00:00', fault['intervalEndUtc'])
        self.assertEqual('no-sensor', fault['status']['reliability'])
        self.assertEqual('fault', fault['status']['eventState'])
        self.assertTrue(fault['status']['fault'])
        self.assertTrue(fault['status']['inAlarm'])  # BACnet: in alarm whenever Event_State is not normal

    def test_high_limit_raises_the_alarm_only_above_the_limit(self):
        now = utc('2026-11-04T16:19:00+00:00')
        for limit, expected in (('80', 'high-limit'), ('90', 'normal')):
            with self.subTest(limit=limit):
                config = copy.deepcopy(self.config)
                next(o for d in config['devices'] for o in d['objects'] if o['valueKey'] == 'plant_steam_header_psig')['highLimit'] = limit
                status = build_values(ThermalModel(), config, now)['plant_steam_header_psig']['status']
                self.assertEqual(expected, status['eventState'])
                self.assertEqual(expected != 'normal', status['inAlarm'])

    def test_invalid_status_calendars_fail(self):
        broken = [
            {'key': 'both', 'weekday': 'Tuesday', 'monthDay': 1, 'startLocal': '02:00', 'endLocal': '03:00', 'valueKeys': ['science_chw_tons']},
            {'key': 'backwards', 'weekday': 'Tuesday', 'startLocal': '04:00', 'endLocal': '03:00', 'valueKeys': ['science_chw_tons']},
            {'key': 'unknown-point', 'weekday': 'Tuesday', 'startLocal': '02:00', 'endLocal': '03:00', 'valueKeys': ['nothing']},
            {'key': 'unknown-state', 'weekday': 'Tuesday', 'startLocal': '02:00', 'endLocal': '03:00', 'valueKeys': ['science_chw_tons'], 'eventState': 'odd'},
        ]
        for scenario in broken:
            with self.subTest(scenario=scenario['key']):
                config = copy.deepcopy(self.config)
                config['statusScenarios'] = [scenario]
                with self.assertRaises(ValueError):
                    build_values(ThermalModel(), config, utc('2026-11-04T16:19:00+00:00'))

    def test_distribution_losses_and_native_units(self):
        model = ThermalModel()
        values = build_values(model, self.config, datetime(2026, 11, 4, 16, 19, tzinfo=timezone.utc))
        self.assertEqual(200, values['plant_chw_ton_hours']['value'])
        self.assertEqual(200, values['plant_chw_tons']['value'])
        self.assertEqual(50, values['plant_steam_klb']['value'])
        self.assertEqual(50000, values['plant_steam_lb_per_hour']['value'])
        self.assertEqual(4.496403, values['plant_condensate_kgal']['value'])
        self.assertEqual('2026-11-04T16:00:00+00:00', values['science_chw_tons']['intervalEndUtc'])
        self.assertEqual('2026-11-04T16:15:00+00:00', values['plant_steam_header_psig']['intervalEndUtc'])
        self.assertEqual(4, len(model.reads))
        self.assertTrue(all(read[3] == 60 for read in model.reads))

    def test_same_closed_intervals_are_stable_between_polls(self):
        first = build_values(ThermalModel(), self.config, datetime.fromisoformat('2026-11-04T16:19:01+00:00'))
        second = build_values(ThermalModel(), self.config, datetime.fromisoformat('2026-11-04T16:29:59+00:00'))
        self.assertEqual(first, second)

    def test_repeated_hour_preserves_two_physical_utc_ends(self):
        first = build_values(ThermalModel(), self.config, datetime.fromisoformat('2026-11-01T01:10:00-07:00'))
        second = build_values(ThermalModel(), self.config, datetime.fromisoformat('2026-11-01T01:10:00-08:00'))
        self.assertEqual('2026-11-01T08:00:00+00:00', first['science_chw_tons']['intervalEndUtc'])
        self.assertEqual('2026-11-01T09:00:00+00:00', second['science_chw_tons']['intervalEndUtc'])

    def test_invalid_clock_or_physical_configuration_fails(self):
        with self.assertRaisesRegex(ValueError, 'timezone-aware'):
            build_values(ThermalModel(), self.config, datetime(2026, 11, 4))
        for field, value in [('steamDistributionLossFraction', '1'), ('chilledWaterDistributionLossFraction', '-0.1'), ('condensatePoundsPerGallon', '0')]:
            with self.subTest(field=field):
                config = copy.deepcopy(self.config)
                config['assumptions'][field] = value
                with self.assertRaises(ValueError):
                    build_values(ThermalModel(), config, datetime.now(timezone.utc))

    def test_actual_canonical_model_drives_science_values(self):
        model = create_model(CONFIG.resolve().parents[2])
        now = datetime.fromisoformat('2025-07-02T17:19:00+00:00')
        values = build_values(model, self.config, now)
        expected = model.meter_value('ntp_science_center_chilled_water', 'chilled_water_ton_hours', now.replace(minute=0), 60)
        self.assertEqual(float(expected.quantize(Decimal('0.000001'))), values['science_chw_ton_hours']['value'])
        self.assertEqual(10, len(values))
        self.assertTrue(all(item['value'] >= 0 for item in values.values()))


if __name__ == '__main__':
    unittest.main()

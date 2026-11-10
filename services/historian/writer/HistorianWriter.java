import com.healthmarketscience.jackcess.ColumnBuilder;
import com.healthmarketscience.jackcess.CursorBuilder;
import com.healthmarketscience.jackcess.DataType;
import com.healthmarketscience.jackcess.Database;
import com.healthmarketscience.jackcess.DatabaseBuilder;
import com.healthmarketscience.jackcess.DateTimeType;
import com.healthmarketscience.jackcess.IndexBuilder;
import com.healthmarketscience.jackcess.IndexCursor;
import com.healthmarketscience.jackcess.Table;
import com.healthmarketscience.jackcess.TableBuilder;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Writes historian rows into an Access database: a row whose key (Channel, UtcTimeStamp) exists is
 * replaced, any other is added. The rows are the CSV that services.historian.rows writes; the
 * database and its table are created on first use. Times are stored as given, wall-clock values with
 * no time zone, as Access keeps them.
 */
public final class HistorianWriter {
    private static final String TABLE = "SyntheticIntervalReadings";
    private static final List<String> COLUMNS = List.of("Channel", "UtcTimeStamp", "TimeStamp", "Value",
            "SourceClassification", "SourceCode", "Reader", "Method", "HistorianTag");
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int BATCH = 1000;

    private HistorianWriter() {
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            System.err.println("Usage: HistorianWriter <rows.csv> <database.accdb>");
            System.exit(2);
        }
        Path rows = Path.of(args[0]);
        Path target = Path.of(args[1]);
        try (Database database = Files.exists(target)
                ? DatabaseBuilder.open(target)
                : DatabaseBuilder.newDatabase(target).setFileFormat(Database.FileFormat.V2016).create()) {
            database.setDateTimeType(DateTimeType.LOCAL_DATE_TIME);
            Table table = database.getTable(TABLE);
            if (table == null) {
                table = createTable(database);
            }
            IndexCursor byKey = CursorBuilder.createPrimaryKeyCursor(table);
            List<Object[]> added = new ArrayList<>();
            int replaced = 0;
            try (BufferedReader reader = Files.newBufferedReader(rows, StandardCharsets.UTF_8)) {
                String header = reader.readLine();
                if (header == null || !split(header).equals(COLUMNS)) {
                    throw new IOException("Unexpected historian row header: " + header);
                }
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    Object[] row = row(split(line));
                    if (byKey.findFirstRowByEntry(row[0], row[1])) {
                        byKey.updateCurrentRow(row);
                        replaced++;
                    } else {
                        added.add(row);
                    }
                }
            }
            for (int start = 0; start < added.size(); start += BATCH) {
                table.addRows(added.subList(start, Math.min(added.size(), start + BATCH)));
            }
            System.out.println("{\"added\":" + added.size() + ",\"replaced\":" + replaced + ",\"rows\":" + table.getRowCount() + "}");
        }
    }

    private static Table createTable(Database database) throws IOException {
        return new TableBuilder(TABLE)
                .addColumn(new ColumnBuilder("Channel", DataType.TEXT).setLengthInUnits(64))
                .addColumn(new ColumnBuilder("UtcTimeStamp", DataType.SHORT_DATE_TIME))
                .addColumn(new ColumnBuilder("TimeStamp", DataType.SHORT_DATE_TIME))
                .addColumn(new ColumnBuilder("Value", DataType.DOUBLE))
                .addColumn(new ColumnBuilder("SourceClassification", DataType.TEXT).setLengthInUnits(16))
                .addColumn(new ColumnBuilder("SourceCode", DataType.TEXT).setLengthInUnits(16))
                .addColumn(new ColumnBuilder("Reader", DataType.TEXT).setLengthInUnits(64))
                .addColumn(new ColumnBuilder("Method", DataType.TEXT).setLengthInUnits(32))
                .addColumn(new ColumnBuilder("HistorianTag", DataType.TEXT).setLengthInUnits(64))
                .setPrimaryKey("Channel", "UtcTimeStamp")
                .addIndex(new IndexBuilder("ChannelTimeStamp").addColumns("Channel", "TimeStamp"))
                .toTable(database);
    }

    private static Object[] row(List<String> fields) throws IOException {
        if (fields.size() != COLUMNS.size()) {
            throw new IOException("A historian row needs " + COLUMNS.size() + " fields, not " + fields.size());
        }
        return new Object[] {
            fields.get(0),
            LocalDateTime.parse(fields.get(1), STAMP),
            LocalDateTime.parse(fields.get(2), STAMP),
            Double.valueOf(fields.get(3)),
            blankToNull(fields.get(4)),
            blankToNull(fields.get(5)),
            blankToNull(fields.get(6)),
            blankToNull(fields.get(7)),
            fields.get(8),
        };
    }

    /** The rows hold no commas or quotes, so a field is everything between commas. */
    private static List<String> split(String line) throws IOException {
        if (line.indexOf('"') >= 0) {
            throw new IOException("Quoted historian fields are not expected: " + line);
        }
        return Arrays.asList(line.split(",", -1));
    }

    private static String blankToNull(String value) {
        return value.isEmpty() ? null : value;
    }
}

ARG SOURCE_IMAGE=hippo-northlake-sources:local
FROM ${SOURCE_IMAGE}
WORKDIR /app
COPY services/handheld /app/services/handheld
# The Northlake look: the shared page chrome and the brand system it imports.
# Copied over the source image's older copy so the handheld follows them
# without rebuilding the source producer.
COPY identity/branding /app/identity/branding
COPY brands/northlake /app/brands/northlake
ENV NORTHLAKE_HANDHELD_STATE=/handheld NORTHLAKE_SOURCE_STATE=/source NORTHLAKE_HANDHELD_TARGETS=/handheld/targets.json
VOLUME /handheld
EXPOSE 8080
ENTRYPOINT ["python", "-m", "services.handheld"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]

ARG SOURCE_IMAGE=hippo-northlake-sources:local

# The Access writer: Jackcess, a pure-Java library for Access files, checked against its Maven Central hash.
FROM eclipse-temurin:21-jdk@sha256:ebfbb18d11ff163ee83b21258acf12248af48d22a0fdfdc68fa1a1516c05976a AS writer
WORKDIR /build
ADD --checksum=sha256:19a7494a56f439a57fda85c059b019b665802085cec5ae8186d1e028cc1bdfbc \
    https://repo1.maven.org/maven2/com/healthmarketscience/jackcess/jackcess/5.0.4/jackcess-5.0.4.jar lib/jackcess-5.0.4.jar
COPY services/historian/writer/HistorianWriter.java src/
RUN javac --release 21 -cp lib/jackcess-5.0.4.jar -d classes src/HistorianWriter.java

# The historian derives from the published release's source image, so its values use that release's model.
FROM ${SOURCE_IMAGE}
COPY --from=eclipse-temurin:21-jre@sha256:0b99b3376fbb50dbf9c0af8535fdd5b8eb0d3fdfc8b1e4967f383b6919f6901a /opt/java/openjdk /opt/java/openjdk
COPY --from=writer /build/lib /opt/historian/lib
COPY --from=writer /build/classes /opt/historian/classes
WORKDIR /app
COPY services/historian /app/services/historian
ENV JAVA_HOME=/opt/java/openjdk PATH=/opt/java/openjdk/bin:$PATH NORTHLAKE_HISTORIAN_ROOT=/historian NORTHLAKE_SOURCE_STATE=/source
ENTRYPOINT ["python", "-m", "services.historian"]
CMD ["run"]

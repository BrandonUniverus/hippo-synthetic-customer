ARG SOURCE_IMAGE=hippo-northlake-sources:local
FROM ${SOURCE_IMAGE} AS values
COPY services/bacnet/__init__.py services/bacnet/producer.py services/bacnet/bindings.json /app/services/bacnet/
ENTRYPOINT ["python", "-m", "services.bacnet.producer"]
CMD ["--state", "/state"]

FROM mcr.microsoft.com/dotnet/sdk:10.0@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b AS build
WORKDIR /src
COPY services/bacnet/server/ ./
RUN dotnet publish Northlake.Bacnet.csproj -c Release -o /out --nologo

FROM mcr.microsoft.com/dotnet/runtime:10.0@sha256:a3f9f81954b9c810af2ed18849716c8dc74a4707bd0907fdbd69be81554c0f30 AS server
WORKDIR /app
COPY --from=build /out/ ./
COPY services/bacnet/bindings.json ./bindings.json
ENTRYPOINT ["dotnet", "Northlake.Bacnet.dll"]
CMD ["/app/bindings.json", "/state", ""]

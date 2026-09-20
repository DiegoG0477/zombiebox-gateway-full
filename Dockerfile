FROM golang:1.25.6-alpine3.23@sha256:98e6cffc31ccc44c7c15d83df1d69891efee8115a5bb7ede2bf30a38af3e3c92 AS build
WORKDIR /src
COPY gateway/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /zombied ./cmd/zombied

FROM scratch
COPY --from=build /zombied /zombied
USER 65532:65532
EXPOSE 8090
ENTRYPOINT ["/zombied"]
CMD ["-listen", "0.0.0.0:8090"]

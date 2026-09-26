FROM golang:1.25.6-alpine3.23@sha256:98e6cffc31ccc44c7c15d83df1d69891efee8115a5bb7ede2bf30a38af3e3c92 AS build
WORKDIR /src
COPY gateway/ ./
RUN --mount=type=cache,id=zombie-go-mod,target=/go/pkg/mod,sharing=locked \
    --mount=type=cache,id=zombie-go-build,target=/root/.cache/go-build,sharing=locked \
    CGO_ENABLED=0 GOMAXPROCS=2 go build -p 2 -trimpath -ldflags="-s -w" -o /zombied ./cmd/zombied

FROM alpine:3.23@sha256:85fe1e81d6758c208f3e1eed4338a1997e19d4be002d4dd32d3100c9a8c010a0
RUN apk add --no-cache ffmpeg=8.0.1-r1
COPY --from=build /zombied /zombied
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY LICENSE NOTICE /usr/share/doc/zombiebox/
COPY docs/licenses/DIAL-LICENSE /usr/share/doc/zombiebox/DIAL-LICENSE
COPY docs/licenses/go-qrcode-LICENSE /usr/share/doc/zombiebox/go-qrcode-LICENSE
COPY docs/licenses/miekg-dns-LICENSE /usr/share/doc/zombiebox/miekg-dns-LICENSE
COPY docs/licenses/golang-x-net-LICENSE /usr/share/doc/zombiebox/golang-x-net-LICENSE
COPY docs/licenses/golang-x-sys-LICENSE /usr/share/doc/zombiebox/golang-x-sys-LICENSE
COPY third_party/THIRD_PARTY_NOTICES.md /usr/share/doc/zombiebox/THIRD_PARTY_NOTICES.md
USER 65532:65532
EXPOSE 8090
ENTRYPOINT ["/zombied"]
CMD ["-listen", "0.0.0.0:8090", "-state", "/data/gateway.db", "-media-dir", "/media", "-config", "/config/providers.json"]

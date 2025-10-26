FROM golang:1.17.3-alpine3.14 as build-env
LABEL maintainer="ForestVPN.com <support@forestvpn.com>"

RUN apk add --no-cache git gcc
RUN mkdir /app

WORKDIR /app

COPY . .

# Упрощаем сборку - не используем git tags
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
      -ldflags "-X main.appVersion=1.0.0" \
      -o wgrest cmd/wgrest-server/main.go

FROM alpine:3.14
LABEL maintainer="ForestVPN.com <support@forestvpn.com>"

RUN apk add --no-cache ca-certificates tzdata

COPY --from=build-env /app/wgrest .

EXPOSE 8000/tcp

# Не используем USER, чтобы иметь права на чтение WireGuard конфигов
# USER 1001

ENTRYPOINT ["./wgrest"]
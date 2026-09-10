# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

ENV GOPROXY=https://goproxy.cn,direct

COPY go.mod go.sum* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o pagegen ./cmd/server

# Final stage
FROM alpine:3.19

RUN apk --no-cache add curl ca-certificates

WORKDIR /app

COPY --from=builder /app/pagegen .
COPY templates/ ./templates/

RUN addgroup -g 10001 -S appgroup && \
    adduser -u 10001 -S appuser -G appgroup

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 5555

ENV PORT=5555

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["./pagegen"]

package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/pagegen/internal/config"
	"github.com/pagegen/internal/handler"
	"github.com/pagegen/internal/middleware"
	"github.com/pagegen/internal/session"
)

func main() {
	_ = godotenv.Load()

	cfg := config.Load()

	store := session.NewStore([]byte(cfg.SecretKey))

	mux := handler.NewRouter(cfg, store)

	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      middleware.Chain(mux, middleware.Logger, middleware.Recoverer, middleware.ContentType),
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		log.Printf("pagegen starting on :%s", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("shutdown: %v", err)
	}
	log.Println("stopped")
}

package session

import (
	"crypto/rand"
	"encoding/base64"
	"net/http"
	"sync"
	"time"
)

type Store struct {
	secret []byte
	mu     sync.RWMutex
	sessions map[string]*Session
}

type Session struct {
	Data     map[string]interface{}
	Expiry   time.Time
}

func NewStore(secret []byte) *Store {
	return &Store{
		secret:   secret,
		sessions: make(map[string]*Session),
	}
}

func (s *Store) Get(r *http.Request, name string) (*Session, error) {
	cookie, err := r.Cookie(name)
	if err != nil {
		return s.newSession(), nil
	}

	s.mu.RLock()
	sess, ok := s.sessions[cookie.Value]
	s.mu.RUnlock()

	if !ok || time.Now().After(sess.Expiry) {
		return s.newSession(), nil
	}

	return sess, nil
}

func (s *Store) Save(w http.ResponseWriter, r *http.Request, name string, sess *Session) error {
	cookie, err := r.Cookie(name)
	if err != nil {
		cookie = &http.Cookie{Name: name}
	}

	if cookie.Value == "" {
		cookie.Value = s.generateID()
	}

	sess.Expiry = time.Now().Add(60 * time.Minute)

	s.mu.Lock()
	s.sessions[cookie.Value] = sess
	s.mu.Unlock()

	cookie.Path = "/"
	cookie.HttpOnly = true
	cookie.SameSite = http.SameSiteLaxMode
	http.SetCookie(w, cookie)
	return nil
}

func (s *Store) Clear(w http.ResponseWriter, name string) {
	http.SetCookie(w, &http.Cookie{
		Name:     name,
		Value:    "",
		Path:     "/",
		MaxAge:   -1,
		HttpOnly: true,
	})
}

func (s *Store) newSession() *Session {
	return &Session{
		Data:   make(map[string]interface{}),
		Expiry: time.Now().Add(60 * time.Minute),
	}
}

func (s *Store) generateID() string {
	b := make([]byte, 32)
	rand.Read(b)
	return base64.URLEncoding.EncodeToString(b)
}

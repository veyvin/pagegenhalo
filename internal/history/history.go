package history

import (
	"sync"
	"time"

	"github.com/google/uuid"
)

const MaxHistory = 50

type Record struct {
	ID        string    `json:"id"`
	Title     string    `json:"title"`
	Content   string    `json:"content"`
	CreatedAt string    `json:"created_at"`
	Status    string    `json:"status"`
}

var (
	mu      sync.RWMutex
	records = make([]*Record, 0, MaxHistory)
)

func AddRecord(title, content, status string) string {
	mu.Lock()
	defer mu.Unlock()

	id := uuid.New().String()[:8]
	r := &Record{
		ID:        id,
		Title:     title,
		Content:   content,
		CreatedAt: time.Now().Format(time.RFC3339),
		Status:    status,
	}

	records = append([]*Record{r}, records...)
	if len(records) > MaxHistory {
		records = records[:MaxHistory]
	}
	return id
}

func GetList(limit int) []*Record {
	mu.RLock()
	defer mu.RUnlock()

	if limit > len(records) {
		limit = len(records)
	}

	result := make([]*Record, limit)
	for i := 0; i < limit; i++ {
		r := records[i]
		result[i] = &Record{
			ID:        r.ID,
			Title:     r.Title,
			CreatedAt: r.CreatedAt,
			Status:    r.Status,
		}
	}
	return result
}

func GetOne(id string) *Record {
	mu.RLock()
	defer mu.RUnlock()

	for _, r := range records {
		if r.ID == id {
			return r
		}
	}
	return nil
}

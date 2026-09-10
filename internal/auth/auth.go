package auth

import (
	"crypto/rand"
	"encoding/base32"
	"fmt"
	"net/url"

	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
)

func GetOrCreateSecret(configured string) string {
	if configured != "" {
		return configured
	}
	secret := generateRandomSecret()
	fmt.Printf("WARNING: GOOGLE_AUTH_SECRET not set. Generated temp secret: %s\n", secret)
	return secret
}

func VerifyOTP(token, secret string, window int) bool {
	if len(token) != 6 {
		return false
	}
	key, err := otp.NewKeyFromURL(fmt.Sprintf("otpauth://totp/pagegen:admin?secret=%s&issuer=pagegen", secret))
	if err != nil {
		return false
	}
	return totp.Validate(key.Secret(), token)
}

func GenerateQRCodeURL(secret string) string {
	return fmt.Sprintf(
		"otpauth://totp/OnDayGitHub:%s?secret=%s&issuer=OnDayGitHub",
		url.PathEscape("admin"), secret,
	)
}

func generateRandomSecret() string {
	b := make([]byte, 20)
	rand.Read(b)
	return base32.StdEncoding.EncodeToString(b)
}

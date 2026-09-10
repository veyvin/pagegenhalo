package auth

import (
	"crypto/rand"
	"encoding/base32"
	"fmt"

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

func VerifyOTP(token, secret string) bool {
	if len(token) != 6 {
		return false
	}
	return totp.Validate(secret, token)
}

func GenerateQRCodeURL(secret string) string {
	return fmt.Sprintf(
		"otpauth://totp/PageGen:admin?secret=%s&issuer=PageGen",
		secret,
	)
}

func generateRandomSecret() string {
	b := make([]byte, 20)
	rand.Read(b)
	return base32.StdEncoding.EncodeToString(b)
}

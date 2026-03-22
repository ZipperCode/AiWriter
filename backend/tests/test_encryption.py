import pytest
from cryptography.fernet import InvalidToken

from app.security.encryption import (
    generate_fernet_key,
    encrypt_api_key,
    decrypt_api_key,
)


class TestFernetEncryption:
    """Test suite for Fernet encryption utilities."""

    def test_generate_fernet_key(self):
        """Test that generate_fernet_key returns a valid Fernet key string."""
        key = generate_fernet_key()

        # Should be a string
        assert isinstance(key, str)

        # Should be non-empty
        assert len(key) > 0

        # Should be valid Fernet key format (base64-encoded, 44 chars typically)
        # Verify it can be used to create a Fernet cipher
        from cryptography.fernet import Fernet
        cipher = Fernet(key.encode())
        assert cipher is not None

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt then decrypt returns the original plaintext."""
        key = generate_fernet_key()
        original = "super-secret-api-key-12345"

        # Encrypt
        ciphertext = encrypt_api_key(original, key)
        assert ciphertext != original

        # Decrypt
        decrypted = decrypt_api_key(ciphertext, key)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertext(self):
        """Test that encrypting the same plaintext twice produces different ciphertexts (due to random IV in Fernet)."""
        key = generate_fernet_key()
        plaintext = "test-api-key"

        # Encrypt twice
        ciphertext1 = encrypt_api_key(plaintext, key)
        ciphertext2 = encrypt_api_key(plaintext, key)

        # Should be different due to random IV
        assert ciphertext1 != ciphertext2

        # But both should decrypt to the same plaintext
        assert decrypt_api_key(ciphertext1, key) == plaintext
        assert decrypt_api_key(ciphertext2, key) == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with the wrong key raises InvalidToken."""
        key1 = generate_fernet_key()
        key2 = generate_fernet_key()

        plaintext = "secret-data"
        ciphertext = encrypt_api_key(plaintext, key1)

        # Attempting to decrypt with a different key should fail
        with pytest.raises(InvalidToken):
            decrypt_api_key(ciphertext, key2)

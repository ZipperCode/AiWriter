from cryptography.fernet import Fernet, InvalidToken


def generate_fernet_key() -> str:
    """Generate a new Fernet encryption key.

    Returns:
        str: A valid Fernet key encoded as a UTF-8 string.
    """
    return Fernet.generate_key().decode()


def encrypt_api_key(plaintext: str, key: str) -> str:
    """Encrypt an API key using Fernet symmetric encryption.

    Args:
        plaintext: The API key or secret to encrypt.
        key: The Fernet key (from generate_fernet_key()).

    Returns:
        str: The encrypted ciphertext as a UTF-8 string.

    Raises:
        ValueError: If the key is invalid.
    """
    try:
        cipher = Fernet(key.encode())
        ciphertext = cipher.encrypt(plaintext.encode())
        return ciphertext.decode()
    except Exception as e:
        raise ValueError(f"Encryption failed: {e}")


def decrypt_api_key(ciphertext: str, key: str) -> str:
    """Decrypt a Fernet-encrypted API key.

    Args:
        ciphertext: The encrypted ciphertext.
        key: The Fernet key (must match the one used for encryption).

    Returns:
        str: The decrypted plaintext.

    Raises:
        InvalidToken: If the ciphertext is invalid or the key is wrong.
        ValueError: If decryption fails.
    """
    try:
        cipher = Fernet(key.encode())
        plaintext = cipher.decrypt(ciphertext.encode())
        return plaintext.decode()
    except InvalidToken as e:
        raise InvalidToken(f"Decryption failed - invalid key or corrupted ciphertext: {e}")
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")

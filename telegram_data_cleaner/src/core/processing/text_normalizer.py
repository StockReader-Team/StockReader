"""
Persian text normalization using Hazm (with fallback).
"""
import re
from typing import Optional, List

from src.core.logging import get_logger

logger = get_logger(__name__)

# Try to import Hazm, but don't fail if not available
try:
    from hazm import Normalizer, word_tokenize, stopwords_list
    HAZM_AVAILABLE = True
    logger.info("Hazm library loaded successfully")
except ImportError:
    HAZM_AVAILABLE = False
    logger.warning(
        "Hazm library not available. Using fallback text normalization. "
        "Install hazm for better Persian text processing: pip install hazm"
    )


class TextNormalizer:
    """
    Persian text normalizer with Hazm support.

    Features:
    - Character normalization (Arabic to Persian, ZWNJ handling)
    - Stopwords removal
    - Tokenization
    - Fallback mode when Hazm is not available
    """

    def __init__(self, use_hazm: bool = True, remove_stopwords: bool = True):
        """
        Initialize text normalizer.

        Args:
            use_hazm: Use Hazm library if available (default: True)
            remove_stopwords: Remove Persian stopwords (default: True)
        """
        self.use_hazm = use_hazm and HAZM_AVAILABLE
        self.remove_stopwords_flag = remove_stopwords

        if self.use_hazm:
            # Initialize Hazm components
            self.normalizer = Normalizer(
                persian_numbers=True,
                persian_style=True,
                remove_extra_spaces=True,
                remove_diacritics=True,
            )
            self.stopwords = set(stopwords_list()) if remove_stopwords else set()
            logger.info("TextNormalizer initialized with Hazm")
        else:
            self.normalizer = None
            self.stopwords = self._get_basic_stopwords() if remove_stopwords else set()
            logger.info("TextNormalizer initialized with fallback mode")

    @staticmethod
    def _get_basic_stopwords() -> set[str]:
        """
        Get basic Persian stopwords for fallback mode.

        Returns:
            Set of common stopwords
        """
        return {
            "و", "در", "به", "از", "که", "این", "را", "با", "است", "برای",
            "آن", "یک", "خود", "تا", "کرد", "بر", "هم", "نیز", "ای", "شد",
            "یا", "هر", "کن", "دارد", "ها", "شده", "بود", "خواهد", "شود",
            "باشد", "می", "کند", "ان", "کرده", "کنند", "گفت", "بین", "پیش",
            "پس", "اگر", "همه", "صورت", "یکی", "هستند", "بی", "من", "ما",
            "تو", "شما", "او", "آنها", "چه", "چی", "کجا", "چرا", "چگونه",
        }

    def _normalize_with_hazm(self, text: str) -> str:
        """
        Normalize text using Hazm library.

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        try:
            # Normalize text
            normalized = self.normalizer.normalize(text)

            # Remove stopwords if requested
            if self.remove_stopwords_flag and self.stopwords:
                tokens = word_tokenize(normalized)
                tokens = [token for token in tokens if token not in self.stopwords]
                normalized = " ".join(tokens)

            return normalized.strip()

        except Exception as e:
            logger.error(f"Hazm normalization failed: {e}. Using fallback.")
            return self._normalize_fallback(text)

    def _normalize_fallback(self, text: str) -> str:
        """
        Fallback normalization without Hazm.

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        try:
            # Arabic to Persian character conversion
            text = text.replace("ك", "ک")
            text = text.replace("ي", "ی")
            text = text.replace("ى", "ی")
            text = text.replace("ؤ", "و")
            text = text.replace("إ", "ا")
            text = text.replace("أ", "ا")
            text = text.replace("ٱ", "ا")
            text = text.replace("ة", "ه")

            # Remove Arabic diacritics
            text = re.sub(r'[\u064B-\u065F]', '', text)

            # Normalize ZWNJ (Zero Width Non-Joiner)
            text = text.replace('\u200c', ' ')  # Replace ZWNJ with space

            # Normalize multiple spaces
            text = re.sub(r'\s+', ' ', text)

            # Remove URLs
            text = re.sub(r'http\S+|www\.\S+', '', text)

            # Remove mentions (keep hashtags for matching)
            text = re.sub(r'@\w+', '', text)
            # Keep hashtag text, just remove the # symbol
            text = re.sub(r'#(\w+)', r'\1', text)

            # Remove extra punctuation
            text = re.sub(r'[!]{2,}', '!', text)
            text = re.sub(r'[?]{2,}', '?', text)
            text = re.sub(r'\.{2,}', '…', text)

            # Remove stopwords if requested
            if self.remove_stopwords_flag and self.stopwords:
                # Simple tokenization (split by space)
                tokens = text.split()
                tokens = [token for token in tokens if token not in self.stopwords]
                text = " ".join(tokens)

            return text.strip()

        except Exception as e:
            logger.error(f"Fallback normalization failed: {e}")
            return text.strip()

    def normalize(self, text: Optional[str]) -> Optional[str]:
        """
        Normalize Persian text.

        Args:
            text: Input text

        Returns:
            Normalized text or None if input is None/empty
        """
        if not text or not text.strip():
            return None

        try:
            if self.use_hazm:
                return self._normalize_with_hazm(text)
            else:
                return self._normalize_fallback(text)

        except Exception as e:
            logger.error(f"Text normalization failed: {e}")
            return text.strip()  # Return original text on failure

    def tokenize(self, text: Optional[str]) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        if not text or not text.strip():
            return []

        try:
            if self.use_hazm:
                # Use Hazm tokenizer
                return word_tokenize(text)
            else:
                # Simple tokenization
                normalized = self._normalize_fallback(text)
                return [
                    token for token in normalized.split()
                    if token and not token.isspace()
                ]

        except Exception as e:
            logger.error(f"Tokenization failed: {e}")
            return text.split()

    def get_word_count(self, text: Optional[str]) -> int:
        """
        Count words in text.

        Args:
            text: Input text

        Returns:
            Word count
        """
        return len(self.tokenize(text))

    def get_char_count(self, text: Optional[str], include_spaces: bool = False) -> int:
        """
        Count characters in text.

        Args:
            text: Input text
            include_spaces: Include spaces in count (default: False)

        Returns:
            Character count
        """
        if not text:
            return 0

        if include_spaces:
            return len(text)
        else:
            return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

    def clean_text(self, text: Optional[str]) -> Optional[str]:
        """
        Deep clean text (remove URLs, mentions, hashtags, etc.).

        Args:
            text: Input text

        Returns:
            Cleaned text
        """
        if not text or not text.strip():
            return None

        try:
            # Remove URLs
            text = re.sub(r'http\S+|www\.\S+', '', text)

            # Remove email addresses
            text = re.sub(r'\S+@\S+', '', text)

            # Remove mentions
            text = re.sub(r'@\w+', '', text)

            # Remove hashtags (keep the text, remove #)
            text = re.sub(r'#(\w+)', r'\1', text)

            # Remove phone numbers (basic pattern)
            text = re.sub(r'\+?\d{10,}', '', text)

            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)

            return text.strip() or None

        except Exception as e:
            logger.error(f"Text cleaning failed: {e}")
            return text.strip()

    def is_hazm_available(self) -> bool:
        """Check if Hazm is available and being used."""
        return self.use_hazm

    def get_stats(self, text: Optional[str]) -> dict[str, int]:
        """
        Get text statistics.

        Args:
            text: Input text

        Returns:
            Dict with statistics (word_count, char_count, etc.)
        """
        if not text:
            return {
                "word_count": 0,
                "char_count": 0,
                "char_count_with_spaces": 0,
                "token_count": 0,
            }

        tokens = self.tokenize(text)

        return {
            "word_count": len(tokens),
            "char_count": self.get_char_count(text, include_spaces=False),
            "char_count_with_spaces": self.get_char_count(text, include_spaces=True),
            "token_count": len(tokens),
        }

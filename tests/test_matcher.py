"""Unit tests for contract matching engine."""

import unittest
from src.matcher import ContractMatcher


class TestContractMatcher(unittest.TestCase):
    """Test cases for fuzzy contract matching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.matcher = ContractMatcher(threshold=85.0)
    
    def test_initialization(self):
        """Test matcher initializes with correct threshold."""
        self.assertEqual(self.matcher.threshold, 85.0)
        
        # Test custom threshold
        custom_matcher = ContractMatcher(threshold=70.0)
        self.assertEqual(custom_matcher.threshold, 70.0)
    
    def test_normalize_title_lowercase(self):
        """Test title normalization converts to lowercase."""
        title = "Will Trump Win 2024?"
        normalized = self.matcher.normalize_title(title)
        self.assertEqual(normalized, "trump win 2024")
    
    def test_normalize_title_removes_punctuation(self):
        """Test title normalization removes punctuation."""
        title = "Will Trump win? Yes or No!"
        normalized = self.matcher.normalize_title(title)
        self.assertNotIn("?", normalized)
        self.assertNotIn("!", normalized)
    
    def test_normalize_title_removes_prefixes(self):
        """Test title normalization removes common prefixes."""
        test_cases = [
            ("Will Trump win?", "trump win"),
            ("Does Biden lead?", "biden lead"),
            ("Is it raining?", "it raining"),
        ]
        
        for original, expected in test_cases:
            normalized = self.matcher.normalize_title(original)
            self.assertEqual(normalized, expected)
    
    def test_normalize_title_collapses_whitespace(self):
        """Test title normalization collapses multiple spaces."""
        title = "Will   Trump    win    election"
        normalized = self.matcher.normalize_title(title)
        self.assertEqual(normalized, "trump win election")
    
    def test_find_matches_identical(self):
        """Test matching identical contracts."""
        kalshi_markets = [
            {'title': 'Will Trump win 2024?', 'id': 'TRUMP-2024'}
        ]
        polymarket_markets = [
            {'question': 'Will Trump win 2024?', 'id': 'trump-2024'}
        ]
        
        matches = self.matcher.find_matches(kalshi_markets, polymarket_markets)
        
        self.assertEqual(len(matches), 1)
        kalshi, poly, score = matches[0]
        self.assertEqual(kalshi['id'], 'TRUMP-2024')
        self.assertEqual(poly['id'], 'trump-2024')
        self.assertGreater(score, 90)  # Should be high similarity
    
    def test_find_matches_similar(self):
        """Test matching similar but not identical contracts."""
        kalshi_markets = [
            {'title': 'Trump to win 2024 election', 'id': 'TRUMP-WIN'}
        ]
        polymarket_markets = [
            {'question': 'Will Trump win the 2024 election?', 'id': 'trump-election'}
        ]
        
        matches = self.matcher.find_matches(kalshi_markets, polymarket_markets)
        
        # Should match due to similar words
        self.assertGreater(len(matches), 0)
        if matches:
            _, _, score = matches[0]
            self.assertGreater(score, 75)  # Decent similarity
    
    def test_find_matches_no_match(self):
        """Test no match for completely different contracts."""
        kalshi_markets = [
            {'title': 'Will Trump win 2024?', 'id': 'TRUMP-2024'}
        ]
        polymarket_markets = [
            {'question': 'Will it rain tomorrow?', 'id': 'rain-tomorrow'}
        ]
        
        matches = self.matcher.find_matches(kalshi_markets, polymarket_markets)
        
        # Should not match
        self.assertEqual(len(matches), 0)
    
    def test_find_matches_threshold(self):
        """Test that threshold is respected."""
        strict_matcher = ContractMatcher(threshold=95.0)
        
        kalshi_markets = [
            {'title': 'Trump wins 2024', 'id': 'TRUMP'}
        ]
        polymarket_markets = [
            {'question': 'Trump victory in 2024', 'id': 'trump-win'}
        ]
        
        matches = strict_matcher.find_matches(kalshi_markets, polymarket_markets)
        
        # High threshold might reject this match
        if matches:
            _, _, score = matches[0]
            self.assertGreaterEqual(score, 95.0)
    
    def test_find_matches_multiple(self):
        """Test matching multiple contracts."""
        kalshi_markets = [
            {'title': 'Trump wins 2024', 'id': 'TRUMP-2024'},
            {'title': 'Biden leads polls', 'id': 'BIDEN-POLLS'},
            {'title': 'Rain tomorrow', 'id': 'RAIN-TOM'}
        ]
        polymarket_markets = [
            {'question': 'Will Trump win 2024?', 'id': 'trump-win'},
            {'question': 'Biden polling ahead', 'id': 'biden-lead'},
            {'question': 'Tomorrow rain', 'id': 'rain'}
        ]
        
        matches = self.matcher.find_matches(kalshi_markets, polymarket_markets)
        
        # Should find multiple matches
        self.assertGreater(len(matches), 0)
        self.assertLessEqual(len(matches), 3)
    
    def test_find_matches_word_order(self):
        """Test matching handles different word order."""
        kalshi_markets = [
            {'title': 'Trump wins election 2024', 'id': 'A'}
        ]
        polymarket_markets = [
            {'question': '2024 election Trump wins', 'id': 'B'}
        ]
        
        matches = self.matcher.find_matches(kalshi_markets, polymarket_markets)
        
        # token_sort_ratio should handle word order
        self.assertEqual(len(matches), 1)
        _, _, score = matches[0]
        self.assertGreater(score, 85)


class TestTitleNormalization(unittest.TestCase):
    """Test edge cases in title normalization."""
    
    def setUp(self):
        self.matcher = ContractMatcher()
    
    def test_empty_title(self):
        """Test handling of empty titles."""
        normalized = self.matcher.normalize_title("")
        self.assertEqual(normalized, "")
    
    def test_only_punctuation(self):
        """Test titles with only punctuation."""
        normalized = self.matcher.normalize_title("???!!!")
        self.assertEqual(normalized, "")
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        title = "Will Trump win 2024? 🇺🇸"
        normalized = self.matcher.normalize_title(title)
        # Should handle gracefully (emojis removed or kept)
        self.assertIn("trump", normalized)
        self.assertIn("win", normalized)
    
    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        title = "Will S&P 500 reach 5000?"
        normalized = self.matcher.normalize_title(title)
        self.assertIn("500", normalized)
        self.assertIn("5000", normalized)
    
    def test_special_characters(self):
        """Test handling of special characters."""
        title = "Will BTC/USD > $50,000?"
        normalized = self.matcher.normalize_title(title)
        # Should preserve important characters or handle gracefully
        self.assertIsInstance(normalized, str)


class TestMatchScoring(unittest.TestCase):
    """Test match scoring logic."""
    
    def setUp(self):
        self.matcher = ContractMatcher(threshold=70.0)
    
    def test_exact_match_score(self):
        """Test that exact matches get high scores."""
        kalshi = [{'title': 'Trump wins 2024', 'id': 'A'}]
        poly = [{'question': 'Trump wins 2024', 'id': 'B'}]
        
        matches = self.matcher.find_matches(kalshi, poly)
        
        self.assertEqual(len(matches), 1)
        _, _, score = matches[0]
        self.assertGreater(score, 95)
    
    def test_partial_match_score(self):
        """Test scoring of partial matches."""
        kalshi = [{'title': 'Trump wins presidential election', 'id': 'A'}]
        poly = [{'question': 'Trump wins', 'id': 'B'}]
        
        matches = self.matcher.find_matches(kalshi, poly)
        
        if matches:
            _, _, score = matches[0]
            # Partial match should have lower score
            self.assertLess(score, 100)
            self.assertGreater(score, 50)


if __name__ == '__main__':
    unittest.main()

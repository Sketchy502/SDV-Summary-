from sdv.parsers.wordfilter.logic import Censor


class TestWordfilter:
    censor = Censor()

    def test_wordfilter_safe_word(self):
        """
        Ensure words not on the filter list are unchanged.
        """

        test_text = "Hello"
        result = self.censor.censor(test_text)
        assert result == test_text

    def test_wordfilter_unsafe_word(self):
        """
        Ensure words on the filter list are censored and all characters are from Censor.censorchars.
        """

        test_text = "fuck"
        result = self.censor.censor(test_text)
        assert result != test_text
        assert all(char in self.censor.censorchars for char in result)

    def test_wordfilter_unsafe_substring(self):
        """
        Ensure substrings are also censored.
        """

        test_text = "scunthorpe"
        result = self.censor.censor(test_text)
        assert result != test_text

    def test_wordfilter_none_input(self):
        """
        Ensure None input returns None
        """

        test_text = None
        result = self.censor.censor(test_text)
        assert result is None

    def test_wordfilter_int_input(self):
        """
        Ensure None input returns None
        """

        test_text = 1
        result = self.censor.censor(test_text)
        assert result is 1

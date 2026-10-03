import unittest
from unittest.mock import patch

from scripts import fetch_and_build as builder


class MovieMetadataTests(unittest.TestCase):
    def build_movie(self, **metadata):
        data = {
            "theater": {"name": "Test Theater", "address": "Test Address"},
            "now_showing": [{"movieId": 1, "title": "Test Movie", **metadata}],
            "schedules": [{
                "movieId": 1,
                "date": "2026-10-03",
                "theaterName": "Cinema 1",
                "showtimes": ["13:00", "15:00"],
            }],
        }
        with patch.object(builder, "fetch_ctc", return_value=data), \
                patch.object(builder, "imdb_lookup", return_value=None):
            return builder.build("2026-10-03")

    def test_missing_metadata_keeps_schedule(self):
        output = self.build_movie()
        self.assertIn('data-label="Rating / Runtime"> &middot; </td>', output)
        self.assertIn('data-label="Movie">Test Movie</td>', output)
        self.assertIn('data-label="Cinema">Cinema 1</td>', output)
        self.assertIn('data-label="Showtimes">13:00, 15:00</td>', output)

    def test_unusable_metadata_renders_blank(self):
        for field in ("mtrcb_rating", "running_time"):
            for value in (None, "", 120, False, [], {}):
                with self.subTest(field=field, value=value):
                    metadata = {"mtrcb_rating": "PG", "running_time": "120 mins"}
                    metadata[field] = value
                    output = self.build_movie(**metadata)
                    expected = " &middot; 120 mins" if field == "mtrcb_rating" else "PG &middot; "
                    self.assertIn(f'data-label="Rating / Runtime">{expected}</td>', output)
                    self.assertIn('data-label="Showtimes">13:00, 15:00</td>', output)

    def test_valid_metadata_remains_escaped(self):
        output = self.build_movie(mtrcb_rating='PG <&"', running_time='120 <&" mins')
        self.assertIn(
            'data-label="Rating / Runtime">PG &lt;&amp;&quot; &middot; 120 &lt;&amp;&quot; mins</td>',
            output,
        )


if __name__ == "__main__":
    unittest.main()

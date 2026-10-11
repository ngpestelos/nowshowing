import unittest
from unittest.mock import call, patch

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


class GatewayMallTests(unittest.TestCase):
    date = "2026-10-11"

    def gateway_data(self):
        # Representative fields from the verified Gateway Mall API for this date.
        return {
            "theater": {"name": "Gateway Mall", "address": "Araneta Center, Cubao"},
            "now_showing": [{
                "movieId": 21452, "title": "Always Yours, Never Mine",
                "mtrcb_rating": "PG", "running_time": "1 hr 52 min",
            }],
            "schedules": [{
                "movieId": 21452, "date": self.date,
                "theaterName": "Gateway Cineplex 1",
                "showtimes": ["1:45 PM", "4:05 PM", "6:20 PM"],
            }],
        }

    def build_gateway(self, data):
        other = {
            "theater": {"name": "Power Plant", "address": "Rockwell"},
            "now_showing": [{"movieId": 2, "title": "Other Theater Movie"}],
            "schedules": [{
                "movieId": 2, "date": self.date, "theaterName": "Cinema 2",
                "showtimes": ["7:00 PM"],
            }],
        }
        def source(slug, date):
            if slug == "gateway-mall":
                return data
            return other if slug == "power-plant-mall" else None
        with patch.object(builder, "fetch_ctc", side_effect=source) as fetch, \
                patch.object(builder, "imdb_lookup", return_value=None):
            output = builder.build(self.date)
        self.assertIn(call("gateway-mall", self.date), fetch.call_args_list)
        self.assertIn('data-label="Movie">Other Theater Movie</td>', output)
        return output

    def test_gateway_entry_renders_for_metro_manila_filters(self):
        output = self.build_gateway(self.gateway_data())
        self.assertIn('data-theater="Gateway Mall" data-city="metro-manila"', output)
        self.assertIn('<option value="Gateway Mall" data-city="metro-manila">Gateway Mall</option>', output)
        self.assertIn('data-title="always yours, never mine" data-cinema="gateway cineplex 1"', output)
        self.assertIn('data-label="Rating / Runtime">PG &middot; 1 hr 52 min</td>', output)
        self.assertIn('data-label="Cinema">Gateway Cineplex 1</td>', output)
        self.assertIn('data-label="Showtimes">1:45 PM, 4:05 PM, 6:20 PM</td>', output)
        self.assertIn('Schedules for 2026-10-11', output)
        self.assertNotIn('value="Gateway Mall 2"', output)

    def test_other_date_is_not_presented_as_current(self):
        data = self.gateway_data()
        data["now_showing"].append({"movieId": 3, "title": "Yesterday Only"})
        data["schedules"].append({
            "movieId": 3, "date": "2026-10-10", "theaterName": "Gateway Cineplex 10",
            "showtimes": ["11:59 PM"],
        })
        output = self.build_gateway(data)
        self.assertIn('data-title="always yours, never mine"', output)
        self.assertNotIn('Yesterday Only', output)
        self.assertNotIn('11:59 PM', output)

    def test_empty_or_other_date_only_schedule_uses_empty_state(self):
        for schedules in ([], [{**self.gateway_data()["schedules"][0], "date": "2026-10-10"}]):
            with self.subTest(schedules=schedules):
                data = self.gateway_data()
                data["schedules"] = schedules
                output = self.build_gateway(data)
                self.assertIn('<h2>Gateway Mall</h2>', output)
                self.assertIn('No schedule available today.', output)
                self.assertNotIn('Always Yours, Never Mine', output)

    def test_fetch_failure_uses_gateway_fallback_and_preserves_other_theaters(self):
        output = self.build_gateway(None)
        self.assertIn('theater-error" data-theater="Gateway Mall" data-city="metro-manila"', output)
        self.assertIn('Could not load schedule for <strong>Gateway Mall</strong> today', output)
        self.assertIn('<option value="Gateway Mall" data-city="metro-manila">Gateway Mall</option>', output)

    def test_gateway_schedule_survives_missing_metadata(self):
        data = self.gateway_data()
        del data["now_showing"][0]["mtrcb_rating"]
        data["now_showing"][0]["running_time"] = None
        output = self.build_gateway(data)
        self.assertIn('data-label="Rating / Runtime"> &middot; </td>', output)
        self.assertIn('data-label="Showtimes">1:45 PM, 4:05 PM, 6:20 PM</td>', output)


if __name__ == "__main__":
    unittest.main()

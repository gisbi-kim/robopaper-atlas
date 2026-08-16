import unittest
from unittest.mock import patch

from _doi_less_checkpoint import normalize_title, paper_key
from step2_openalex import _seed_from_venue_bulk, _title_match_is_valid, _update_entry


class DoiLessEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.paper = {
            "venue": "CoRL",
            "year": "2017",
            "title": "CARLA: An Open Urban Driving Simulator.",
            "dblp_key": "conf/corl/DosovitskiyRCLK17",
        }

    def test_normalize_title_ignores_punctuation_and_case(self):
        self.assertEqual(
            normalize_title("CARLA: An Open Urban Driving Simulator."),
            normalize_title("Carla — an open urban-driving simulator"),
        )

    def test_paper_key_prefers_dblp_key(self):
        self.assertEqual(
            paper_key(self.paper),
            "dblp:conf/corl/DosovitskiyRCLK17",
        )

    def test_exact_dblp_id_accepts_minor_title_formatting_change(self):
        work = {
            "title": "CARLA - An Open Urban Driving Simulator",
            "year": 2017,
            "externalIds": {"DBLP": "conf/corl/DosovitskiyRCLK17"},
        }
        valid, _ = _title_match_is_valid(self.paper, work)
        self.assertTrue(valid)

    def test_wrong_year_is_rejected(self):
        work = {
            "title": "CARLA: An Open Urban Driving Simulator",
            "year": 2024,
            "externalIds": {"DBLP": "conf/corl/DosovitskiyRCLK17"},
        }
        valid, _ = _title_match_is_valid(self.paper, work)
        self.assertFalse(valid)

    def test_exact_title_accepts_adjacent_preprint_year(self):
        work = {
            "title": "CARLA: An Open Urban Driving Simulator",
            "year": 2016,
            "externalIds": {"ArXiv": "1601.00001"},
        }
        valid, _ = _title_match_is_valid(self.paper, work)
        self.assertTrue(valid)

    def test_update_entry_keeps_zero_citations(self):
        entry = {}
        _update_entry(entry, {
            "paperId": "abc123",
            "citationCount": 0,
            "influentialCitationCount": 0,
            "abstract": "Example abstract",
            "fieldsOfStudy": ["Computer Science"],
        })
        self.assertEqual(entry["cited_by_s2"], 0)
        self.assertEqual(entry["s2_paper_id"], "abc123")
        self.assertEqual(entry["concepts"], "Computer Science")

    @patch("step2_openalex.save_doi_less_checkpoint")
    @patch("step2_openalex.fetch_venue_bulk")
    def test_venue_bulk_seeds_checkpoint(self, fetch_bulk, _save_checkpoint):
        fetch_bulk.return_value = [{
            "paperId": "carla-s2-id",
            "title": "CARLA: An Open Urban Driving Simulator",
            "year": 2017,
            "citationCount": 2000,
            "externalIds": {"DBLP": "conf/corl/DosovitskiyRCLK17"},
        }]
        checkpoint = {}
        matched = _seed_from_venue_bulk([self.paper], checkpoint)
        self.assertEqual(matched, 1)
        self.assertEqual(
            checkpoint[paper_key(self.paper)]["cited_by_s2"],
            2000,
        )


if __name__ == "__main__":
    unittest.main()

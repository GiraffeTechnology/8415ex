"""Private queue component definitions, not executed or mounted."""
import unittest
from html import escape

from exchange.queue_status_page import WORDS, render_queue_status


class QueueDomain:
    def __init__(self):
        self.reads = 0
        self.legs = [{'legIndex': i, 'registrationStatus': state,
                      'seller': 'PRIVATE-SELLER', 'buyer': 'PRIVATE-BUYER'}
                     for i, state in enumerate(('pending', 'pending', 'pending',
                                                'confirmed', 'not-submitted', '<script>opaque</script>'))]

    def receipt_view(self, receipt_id, now):
        self.reads += 1
        return {'legs': self.legs, 'deferredLegs': [0], 'rejectedLegs': [1]}

    def overdue_requests(self, receipt_id, now):
        return [{'legIndex': 2, 'privateJournal': 'PRIVATE-PROOF'}]


class QueueStatusLocalesTests(unittest.TestCase):
    def test_known_states_and_unknown_are_localized_without_opaque_or_party_fields(self):
        for locale, words in WORDS.items():
            domain = QueueDomain()
            page = render_queue_status(domain, 'receipt-1', locale=locale, now=10)
            self.assertIn('<section lang="' + locale + '">', page)
            for key in ('heading', 'boundary', 'deferred', 'rejected', 'overdue',
                        'confirmed', 'unfiled', 'unknown'):
                self.assertIn(escape(words[key]), page)
            for private in ('PRIVATE-SELLER', 'PRIVATE-BUYER', 'PRIVATE-PROOF',
                            '<script>', 'opaque'):
                self.assertNotIn(private, page)
            self.assertNotIn('<form', page)
            self.assertEqual(domain.reads, 1)

    def test_pending_and_empty_queue_do_not_claim_completion(self):
        domain = QueueDomain()
        domain.legs = [{'legIndex': 7, 'registrationStatus': 'pending'}]
        page = render_queue_status(domain, 'receipt-1', locale='ja')
        self.assertIn(WORDS['ja']['pending'], page)
        domain.legs = []
        self.assertIn(WORDS['ja']['none'], render_queue_status(domain, 'receipt-1', locale='ja'))

    def test_invalid_locale_and_invalid_leg_identity_refuse(self):
        domain = QueueDomain()
        with self.assertRaises(ValueError):
            render_queue_status(domain, 'receipt-1', locale='de')
        self.assertEqual(domain.reads, 0)
        domain.legs = [{'legIndex': '<img>', 'registrationStatus': 'pending'}]
        with self.assertRaises(ValueError):
            render_queue_status(domain, 'receipt-1')

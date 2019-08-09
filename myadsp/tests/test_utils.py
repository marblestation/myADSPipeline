import unittest
import os
import httpretty
from mock import patch

import adsputils as utils
from myadsp import app, utils
from myadsp.models import Base
from ..emails import myADSTemplate

payload = [{'name': 'Query 1',
                    'query_url': 'https://path/to/query',
                    'results': [{"author_norm":["Nantais, J", "Huchra, J"],
                                 "bibcode":"2012yCat..51392620N",
                                 "title":["VizieR Online Data Catalog: Spectroscopy of M81 globular clusters (Nantais+, 2010)"]},
                                {"author_norm":["Huchra, J", "Macri, L"],
                                 "bibcode":"2012ApJS..199...26H",
                                 "title":["The 2MASS Redshift Survey Description and Data Release"]}]},
                    {'name': 'Query 2',
                     'query_url': 'https://path/to/query',
                     'results': [{"author_norm": ["Nantais, J", "Huchra, J"],
                                  "bibcode": "2012yCat..51392620N",
                                  "title": ["VizieR Online Data Catalog: Spectroscopy of M81 globular clusters (Nantais+, 2010)"]},
                                 {"author_norm": ["Huchra, J", "Macri, L"],
                                  "bibcode": "2012ApJS..199...26H",
                                  "title": ["The 2MASS Redshift Survey Description and Data Release"]}]}]

class TestmyADSCelery(unittest.TestCase):
    """
    Tests the application's methods
    """

    postgresql_url_dict = {
        'port': 5432,
        'host': '127.0.0.1',
        'user': 'postgres',
        'database': 'myads_pipeline'
    }
    postgresql_url = 'postgresql://{user}@{host}:{port}/{database}' \
        .format(
        user=postgresql_url_dict['user'],
        host=postgresql_url_dict['host'],
        port=postgresql_url_dict['port'],
        database=postgresql_url_dict['database']
    )

    def setUp(self):
        unittest.TestCase.setUp(self)
        proj_home = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        self.app = app.myADSCelery('test', local_config= \
            {
                'SQLALCHEMY_URL': self.postgresql_url,
                'SQLALCHEMY_ECHO': False,
                'PROJ_HOME': proj_home,
                'TEST_DIR': os.path.join(proj_home, 'myadsp/tests'),
            })
        Base.metadata.bind = self.app._session.get_bind()
        Base.metadata.create_all()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        Base.metadata.drop_all()
        self.app.close_app()

    def test_app(self):
        assert self.app._config.get('SQLALCHEMY_URL') == self.postgresql_url
        assert self.app.conf.get('SQLALCHEMY_URL') == self.postgresql_url

    def test_send_email(self):
        email_addr = 'to@test.com'
        payload_plain = 'plain test'
        payload_html = '<em>html test</em>'
        with patch('smtplib.SMTP_SSL') as mock_smtp:
            msg = utils.send_email(email_addr,
                                   email_template=myADSTemplate,
                                   payload_plain=payload_plain,
                                   payload_html=payload_html)

            self.assertTrue(payload_plain in msg.get_payload()[0].get_payload())
            self.assertTrue(payload_html in msg.get_payload()[1].get_payload())
            self.assertTrue(myADSTemplate.subject == msg.get('subject'))

    @httpretty.activate
    def test_get_user_email(self):
        user_id = 1

        httpretty.register_uri(
            httpretty.GET, self.app._config.get('API_ADSWS_USER_EMAIL') % user_id,
            content_type = 'application/json',
            status=200,
            body='{"id": 1, "email": "test@test.com"}'
        )

        email = utils.get_user_email(userid=None)

        self.assertIsNone(email)

        email = utils.get_user_email(userid=user_id)

        self.assertEquals(email, 'test@test.com')

    def test_get_first_author_formatted(self):
        results_dict = {"bibcode":"2012ApJS..199...26H",
                        "title":["The 2MASS Redshift Survey: Description and Data Release"],
                        "author_norm":["Huchra, J","Macri, L","Masters, K","Jarrett, T","Berlind, P","Calkins, M","Crook, A","Cutri, R","Erdogdu, P","Falco, E","George, T","Hutcheson, C","Lahav, O","Mader, J","Mink, J","Martimbeau, N","Schneider, S","Skrutskie, M","Tokarz, S","Westover, M"]}

        first_author = utils._get_first_author_formatted(results_dict, author_field='author_norm')
        self.assertEquals(first_author, 'Huchra, J,+:')

        results_dict = {"bibcode": "2012ApJS..199...26H",
                        "title": ["The 2MASS Redshift Survey: Description and Data Release"],
                        "author_norm": ["Huchra, J"]}

        first_author = utils._get_first_author_formatted(results_dict, author_field='author_norm')
        self.assertEquals(first_author, 'Huchra, J')

    def test_payload_to_plain(self):

        formatted_payload = utils.payload_to_plain(payload)

        split_payload = formatted_payload.split('\n')
        self.assertEquals(split_payload[0].strip(), 'Query 1 (https://path/to/query)')
        self.assertEquals(split_payload[1].strip(), '2012yCat..51392620N: Nantais, J,+: VizieR Online Data Catalog: Spectroscopy of M81 globular clusters (Nantais+, 2010)')

    def test_payload_to_html(self):

        formatted_payload = utils.payload_to_html(payload, col=1)

        split_payload = formatted_payload.split('\n')
        self.assertIn('class="columnContent"', split_payload[3])
        self.assertEquals(split_payload[4].strip(),
                          '<h3><a href="https://path/to/query" style="color: #1C459B; font-style: italic;font-weight: bold;">Query 1</a></h3>')
        self.assertIn('href="https://ui.adsabs.harvard.edu//abs/2012yCat..51392620N/abstract"', split_payload[5])

        formatted_payload = utils.payload_to_html(payload, col=2)

        split_payload = formatted_payload.split('\n')
        self.assertIn('class="leftColumnContent"', split_payload[3])
        self.assertEquals(split_payload[4].strip(),
                          '<h3><a href="https://path/to/query" style="color: #1C459B; font-style: italic;font-weight: bold;">Query 1</a></h3>')
        self.assertIn('href="https://ui.adsabs.harvard.edu//abs/2012yCat..51392620N/abstract"', split_payload[5])

        formatted_payload = utils.payload_to_html(payload, col=3)
        self.assertIsNone(formatted_payload)


















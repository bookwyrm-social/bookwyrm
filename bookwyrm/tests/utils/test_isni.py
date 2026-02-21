"""test isni connections"""

import requests
import responses
import xml.etree.ElementTree as ET

from django.test import TestCase

from bookwyrm import activitypub, models
from bookwyrm.utils.isni import (
    get_element_text,
    request_isni_data,
    make_name_string,
    get_other_identifier,
    get_external_information_uri,
    get_author_from_isni,
    find_authors_by_name,
    build_author_from_isni,
    augment_author_metadata,
)


class Isni(TestCase):
    """tests for isni methods"""

    @classmethod
    def setUpTestData(cls):
        """test data"""

        cls.payload = '<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/"> <srw:records> <srw:record> <srw:recordSchema>isni-b</srw:recordSchema> <srw:recordPacking>xml</srw:recordPacking> <srw:recordData> <responseRecord><ISNIAssigned><isniUnformatted>1234</isniUnformatted><isniURI>https://isni.org/isni/1234</isniURI><dataConfidence>60</dataConfidence><ISNIMetadata><identity><personOrFiction><personalName><forename>Sam</forename><surname>Smith</surname><nameUse>public</nameUse><source>TEST</source></personalName> <creativeActivity> <creationRole source="MVB">art</creationRole> <creationClass source="MVB">am</creationClass> <titleOfWork source="BOOP"> <title>The @Testing Book</title> </titleOfWork> <titleOfWork source="NLA" subsource="BEEP"> <title>@Sam Smith, enigma</title> </titleOfWork> <titleOfWork source="BEEP" subsource="LCNACO"> <title>The @first in line</title> </titleOfWork> </creativeActivity> <personalNameVariant> <forename>Sammy</forename> <nameTitle>Fake BookWyrm Author</nameTitle> <source>TEST</source> </personalNameVariant> <personalNameVariant> <surname>Smitters</surname> <nameTitle>Fake BookWyrm Author</nameTitle> <source>TEST</source></personalNameVariant> </personOrFiction></identity><otherIdentifierOfIdentity><type>GND</type><identifier>1064851320</identifier><source>MVB</source></otherIdentifierOfIdentity><otherIdentifierOfIdentity><type>beep</type><identifier>boop</identifier><source>TEST</source></otherIdentifierOfIdentity><sources><codeOfSource>VIAF</codeOfSource><sourceIdentifier>999</sourceIdentifier></sources><externalInformation><information>Wikipedia</information><URI>https://fake.wikipedia.org/wiki/Sam_Smith</URI></externalInformation><externalInformation><information>Beep</information><URI>https://example.com</URI></externalInformation></ISNIMetadata></ISNIAssigned></responseRecord> </srw:recordData> <srw:recordPosition>1</srw:recordPosition> </srw:record> </srw:records></srw:searchRetrieveResponse>'

        cls.author = activitypub.Author(
            id="https://isni.org/isni/1234",
            name="Sam Smith",
            isni="1234",
            viafId="999",
            aliases=["Sammy", "Smitters"],
            bio="Fake BookWyrm Author",
            wikipediaLink="https://fake.wikipedia.org/wiki/Sam_Smith",
        )

    def test_get_element_text(self):
        """return the text from an element"""

        text = ET.fromstring("<surname>Sam Smith</surname>")
        self.assertEqual(get_element_text(text), "Sam Smith")

    @responses.activate
    def test_request_isni_data(self):
        """get data from ISNI api"""

        responses.get("http://isni.oclc.org/sru/", "<test>success</test>")
        responses.get("http://isni.oclc.org/sru/", "<test>success</test>")
        payload = request_isni_data("pica.na", "Sam Smith")
        root = ET.fromstring(payload)
        self.assertEqual(root.tag, "test")
        self.assertEqual(root.text, "success")

    @responses.activate
    def test_request_isni_data_with_error(self):
        """what happens if the ISNI request times out?"""

        responses.get("http://isni.oclc.org/sru/", body=requests.exceptions.Timeout())
        self.assertIsNone(request_isni_data("pica.na", "Sam Smith"))

        responses.get(
            "http://isni.oclc.org/sru/", body=requests.exceptions.ConnectionError()
        )
        self.assertIsNone(request_isni_data("pica.na", "Sam Smith"))

        responses.get("http://isni.oclc.org/sru/", body=Exception())
        self.assertIsNone(request_isni_data("pica.na", "Sam Smith"))

    def test_make_name_string(self):
        """test making a name string"""

        string = "<responseRecord><personalName><forename>Sam</forename><surname>Smith</surname> <nameUse>public</nameUse><source>MVB</source></personalName></responseRecord>"
        name = make_name_string(ET.fromstring(string))
        self.assertEqual(name, "Sam Smith")

        string_two = "<responseRecord><personalName><surname>Smith</surname><nameUse>public</nameUse><source>MVB</source></personalName></responseRecord>"
        name_two = make_name_string(ET.fromstring(string_two))
        self.assertEqual(name_two, "Smith")

        string_three = "<responseRecord><personalName><forename>Sam</forename><nameUse>public</nameUse><source>MVB</source></personalName></responseRecord>"
        name_three = make_name_string(ET.fromstring(string_three))
        self.assertEqual(name_three, "Sam")

    def test_get_other_identifier(self):
        """test getting other ids like VIAF"""

        self.assertEqual(
            get_other_identifier(ET.fromstring(self.payload), "beep"), "boop"
        )
        self.assertEqual(
            get_other_identifier(ET.fromstring(self.payload), "VIAF"), "999"
        )

    def test_get_external_information_uri(self):
        """Test get URLs associated with an author from their ISNI record"""

        self.assertEqual(
            get_external_information_uri(ET.fromstring(self.payload), "wikipedia"),
            "https://fake.wikipedia.org/wiki/Sam_Smith",
        )
        self.assertEqual(
            get_external_information_uri(ET.fromstring(self.payload), "BEEP"),
            "https://example.com",
        )

    @responses.activate
    def test_find_authors_by_name(self):
        """Test query the ISNI database for possible author matches by name"""

        responses.get("http://isni.oclc.org/sru/", self.payload)
        self.assertEqual(
            find_authors_by_name("Sam Smith", description=False), [self.author]
        )

        responses.get("http://isni.oclc.org/sru/", self.payload)
        self.assertEqual(
            find_authors_by_name("Sammy Smitters", description=False), [self.author]
        )

        responses.get("http://isni.oclc.org/sru/", body=requests.exceptions.Timeout())
        self.assertEqual(find_authors_by_name("Sammy Smitters", description=False), [])

        # with description=True
        # In this case the "bio" is actually the title of the first book
        # We use this in edit_book only
        responses.get("http://isni.oclc.org/sru/", self.payload)
        isni_authors = find_authors_by_name("Sam Smith", description=True)
        self.assertNotEqual(isni_authors, [self.author])
        self.assertEqual(isni_authors[0].bio, "The first in line")

    @responses.activate
    def test_get_author_from_isni(self):
        """Test find data to populate a new author record from their ISNI"""

        responses.get("http://isni.oclc.org/sru/", self.payload)
        isni_author = get_author_from_isni("1234")
        self.assertEqual(self.author, isni_author)

        responses.get("http://isni.oclc.org/sru/", body=requests.exceptions.Timeout())
        self.assertIsNone(get_author_from_isni("1234"))

    @responses.activate
    def test_build_author_from_isni(self):
        """Test build basic author class object from ISNI URL"""

        responses.get("http://isni.oclc.org/sru/", self.payload)

        self.assertEqual(
            build_author_from_isni("https://isni.org/isni/1234"),
            {"author": self.author},
        )

    @responses.activate
    def test_augment_author_metadata(self):
        responses.get("http://isni.oclc.org/sru/", self.payload)

        author = models.Author.objects.create(
            name="Bob Bobson",
            aliases=["Bobby Bo"],
            isfdb="xx99",
            openlibrary_key="beepboop",
        )

        self.assertIsNone(author.isni)
        self.assertEqual(author.aliases, ["Bobby Bo"])

        augment_author_metadata(author, "1234")

        author.refresh_from_db()

        self.assertEqual(author.name, "Bob Bobson")
        self.assertEqual(author.isfdb, "xx99")
        self.assertEqual(author.openlibrary_key, "beepboop")
        self.assertEqual(author.isni, "1234")
        self.assertEqual(author.aliases, ["Bobby Bo", "Sammy", "Smitters"])

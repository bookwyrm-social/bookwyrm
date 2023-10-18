""" Use the range message from isbn-international to hyphenate ISBNs """
import os
from typing import Optional
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import requests

from bookwyrm import settings


def _get_rules(element: Element) -> list[Element]:
    if (rules_el := element.find("Rules")) is not None:
        return rules_el.findall("Rule")
    return []


class IsbnHyphenator:
    """Class to manage the range message xml file and use it to hyphenate ISBNs"""

    __range_message_url = "https://www.isbn-international.org/export_rangemessage.xml"
    __range_file_path = os.path.join(
        settings.BASE_DIR, "bookwyrm", "isbn", "RangeMessage.xml"
    )
    __element_tree = None

    def update_range_message(self) -> None:
        """Download the range message xml file and save it locally"""
        response = requests.get(self.__range_message_url)
        with open(self.__range_file_path, "w", encoding="utf-8") as file:
            file.write(response.text)
        self.__element_tree = None

    def hyphenate(self, isbn_13: Optional[str]) -> Optional[str]:
        """hyphenate the given ISBN-13 number using the range message"""
        if isbn_13 is None:
            return None

        if self.__element_tree is None:
            self.__element_tree = ElementTree.parse(self.__range_file_path)

        gs1_prefix = isbn_13[:3]
        reg_group = self.__find_reg_group(isbn_13, gs1_prefix)
        if reg_group is None:
            return isbn_13  # failed to hyphenate

        registrant = self.__find_registrant(isbn_13, gs1_prefix, reg_group)
        if registrant is None:
            return isbn_13  # failed to hyphenate

        publication = isbn_13[len(gs1_prefix) + len(reg_group) + len(registrant) : -1]
        check_digit = isbn_13[-1:]
        return "-".join((gs1_prefix, reg_group, registrant, publication, check_digit))

    def __find_reg_group(self, isbn_13: str, gs1_prefix: str) -> Optional[str]:
        if self.__element_tree is None:
            self.__element_tree = ElementTree.parse(self.__range_file_path)

        ucc_prefixes_el = self.__element_tree.find("EAN.UCCPrefixes")
        if ucc_prefixes_el is None:
            return None

        for ean_ucc_el in ucc_prefixes_el.findall("EAN.UCC"):
            if (
                prefix_el := ean_ucc_el.find("Prefix")
            ) is not None and prefix_el.text == gs1_prefix:
                for rule_el in _get_rules(ean_ucc_el):
                    length_el = rule_el.find("Length")
                    if length_el is None:
                        continue
                    length = int(text) if (text := length_el.text) else 0
                    if length == 0:
                        continue

                    range_el = rule_el.find("Range")
                    if range_el is None or range_el.text is None:
                        continue

                    reg_grp_range = [int(x[:length]) for x in range_el.text.split("-")]
                    reg_group = isbn_13[len(gs1_prefix) : len(gs1_prefix) + length]
                    if reg_grp_range[0] <= int(reg_group) <= reg_grp_range[1]:
                        return reg_group
                return None
        return None

    def __find_registrant(
        self, isbn_13: str, gs1_prefix: str, reg_group: str
    ) -> Optional[str]:
        from_ind = len(gs1_prefix) + len(reg_group)

        if self.__element_tree is None:
            self.__element_tree = ElementTree.parse(self.__range_file_path)

        reg_groups_el = self.__element_tree.find("RegistrationGroups")
        if reg_groups_el is None:
            return None

        for group_el in reg_groups_el.findall("Group"):
            if (
                prefix_el := group_el.find("Prefix")
            ) is not None and prefix_el.text == "-".join((gs1_prefix, reg_group)):
                for rule_el in _get_rules(group_el):
                    length_el = rule_el.find("Length")
                    if length_el is None:
                        continue
                    length = int(text) if (text := length_el.text) else 0
                    if length == 0:
                        continue

                    range_el = rule_el.find("Range")
                    if range_el is None or range_el.text is None:
                        continue
                    registrant_range = [
                        int(x[:length]) for x in range_el.text.split("-")
                    ]
                    registrant = isbn_13[from_ind : from_ind + length]
                    if registrant_range[0] <= int(registrant) <= registrant_range[1]:
                        return registrant
                return None
        return None


hyphenator_singleton = IsbnHyphenator()

import os
import requests

from xml.etree import ElementTree
from bookwyrm import settings


class IsbnHyphenator:
    __range_message_url = "https://www.isbn-international.org/export_rangemessage.xml"
    __range_file_path = os.path.join(
        settings.BASE_DIR, "bookwyrm", "isbn", "RangeMessage.xml"
    )
    __element_tree = None

    def update_range_message(self):
        response = requests.get(self.__range_message_url)
        with open(self.__range_file_path, "w", encoding="utf-8") as file:
            file.write(response.text)
        self.__element_tree = None

    def hyphenate(self, isbn_13):
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

    def __find_reg_group(self, isbn_13, gs1_prefix):
        for ean_ucc_el in self.__element_tree.find("EAN.UCCPrefixes").findall(
            "EAN.UCC"
        ):
            if ean_ucc_el.find("Prefix").text == gs1_prefix:
                for rule_el in ean_ucc_el.find("Rules").findall("Rule"):
                    length = int(rule_el.find("Length").text)
                    if length == 0:
                        continue
                    range = [
                        int(x[:length]) for x in rule_el.find("Range").text.split("-")
                    ]
                    reg_group = isbn_13[len(gs1_prefix) : len(gs1_prefix) + length]
                    if range[0] <= int(reg_group) <= range[1]:
                        return reg_group
                return None
        return None

    def __find_registrant(self, isbn_13, gs1_prefix, reg_group):
        from_ind = len(gs1_prefix) + len(reg_group)
        for group_el in self.__element_tree.find("RegistrationGroups").findall("Group"):
            if group_el.find("Prefix").text == "-".join((gs1_prefix, reg_group)):
                for rule_el in group_el.find("Rules").findall("Rule"):
                    length = int(rule_el.find("Length").text)
                    if length == 0:
                        continue
                    range = [
                        int(x[:length]) for x in rule_el.find("Range").text.split("-")
                    ]
                    registrant = isbn_13[from_ind : from_ind + length]
                    if range[0] <= int(registrant) <= range[1]:
                        return registrant
                return None
        return None


hyphenator_singleton = IsbnHyphenator()

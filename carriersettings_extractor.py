#!/usr/bin/env python3

from collections import OrderedDict
from glob import glob
from itertools import product
import os.path
import sys
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

from carrier_settings_pb2 import CarrierSettings, MultiCarrierSettings
from carrier_list_pb2 import CarrierList
from carrierId_pb2 import CarrierList as CarrierIdList

pb_path = sys.argv[1]

android_build_top = sys.argv[2]

apn_out = sys.argv[3]

cc_out = sys.argv[4]

device = sys.argv[5]

android_path_to_carrierid = "packages/providers/TelephonyProvider/assets/latest_carrier_id"
carrier_id_list = CarrierIdList()
carrier_attribute_map = {}
with open(os.path.join(android_build_top, android_path_to_carrierid, 'carrier_list.pb'), 'rb') as pb:
    carrier_id_list.ParseFromString(pb.read())
for carrier_id_obj in carrier_id_list.carrier_id:
    for carrier_attribute in carrier_id_obj.carrier_attribute:
        for carrier_attributes in product(*(
            (s.lower() for s in getattr(carrier_attribute, i) or [''])
            for i in [
                'mccmnc_tuple', 'imsi_prefix_xpattern', 'spn', 'plmn',
                'gid1', 'preferred_apn', 'iccid_prefix',
                'privilege_access_rule',
            ]
        )):
            carrier_attribute_map[carrier_attributes] = \
                carrier_id_obj.canonical_id

carrier_list = CarrierList()
all_settings = {}
carrier_list.ParseFromString(open(os.path.join(pb_path, 'carrier_list.pb'), 'rb').read())
# Load generic settings first
multi_settings = MultiCarrierSettings()
multi_settings.ParseFromString(open(os.path.join(pb_path, 'others.pb'), 'rb').read())
for setting in multi_settings.setting:
    all_settings[setting.canonical_name] = setting
# Load carrier specific files last, to allow overriding generic settings
for filename in glob(os.path.join(pb_path, '*.pb')):
    with open(filename, 'rb') as pb:
        if os.path.basename(filename) == 'carrier_list.pb':
            # Handled above already
            continue
        elif os.path.basename(filename) == 'others.pb':
            # Handled above already
            continue
        else:
            setting = CarrierSettings()
            setting.ParseFromString(pb.read())
            if setting.canonical_name in all_settings:
                print("Overriding generic settings for " + setting.canonical_name, file=sys.stderr)
            all_settings[setting.canonical_name] = setting


# Unfortunately, python processors like xml and lxml, as well as command-line
# utilities like tidy, do not support the exact style used by AOSP for
# apns-full-conf.xml:
#
#  * indent: 2 spaces
#  * attribute indent: 4 spaces
#  * blank lines between elements
#  * attributes after first indented on separate lines
#  * closing tags of multi-line elements on separate, unindented lines
#
# Therefore, we build the file without using an XML processor.


class ApnElement:
    def __init__(self, apn, carrier_id):
        self.apn = apn
        self.carrier_id = carrier_id
        self.attributes = OrderedDict()
        self.add_attributes()

    def add_attribute(self, key, field=None, value=None):
        if value is not None:
            self.attributes[key] = value
        else:
            if field is None:
                field = key
            if self.apn.HasField(field):
                enum_type = self.apn.DESCRIPTOR.fields_by_name[field].enum_type
                value = getattr(self.apn, field)
                if enum_type is None:
                    if isinstance(value, bool):
                        self.attributes[key] = str(value).lower()
                    else:
                        self.attributes[key] = str(value)
                else:
                    self.attributes[key] = \
                        enum_type.values_by_number[value].name

    def add_attributes(self):
        try:
            self.add_attribute(
                'carrier_id',
                value=str(carrier_attribute_map[(
                    self.carrier_id.mcc_mnc,
                    self.carrier_id.imsi,
                    self.carrier_id.spn.lower(),
                    '',
                    self.carrier_id.gid1.lower(),
                    '',
                    '',
                    '',
                )])
            )
        except KeyError:
            pass
        self.add_attribute('mcc', value=self.carrier_id.mcc_mnc[:3])
        self.add_attribute('mnc', value=self.carrier_id.mcc_mnc[3:])
        self.add_attribute('apn', 'value')
        self.add_attribute('proxy')
        self.add_attribute('port')
        self.add_attribute('mmsc')
        self.add_attribute('mmsproxy', 'mmsc_proxy')
        self.add_attribute('mmsport', 'mmsc_proxy_port')
        self.add_attribute('user')
        self.add_attribute('password')
        self.add_attribute('server')
        self.add_attribute('authtype')
        self.add_attribute(
            'type',
            value=','.join(
                apn.DESCRIPTOR.fields_by_name[
                    'type'
                ].enum_type.values_by_number[i].name
                for i in self.apn.type
            ).lower(),
        )
        self.add_attribute('protocol')
        self.add_attribute('roaming_protocol')
        self.add_attribute('bearer_bitmask')
        self.add_attribute('profile_id')
        self.add_attribute('modem_cognitive')
        self.add_attribute('max_conns')
        self.add_attribute('wait_time')
        self.add_attribute('max_conns_time')
        self.add_attribute('mtu')
        mvno = self.carrier_id.WhichOneof('mvno_data')
        if mvno:
            self.add_attribute(
                'mvno_type',
                value='gid' if mvno.startswith('gid') else mvno,
            )
            self.add_attribute(
                'mvno_match_data',
                value=getattr(self.carrier_id, mvno),
            )
        self.add_attribute('apn_set_id')
        # No source for integer carrier_id?
        self.add_attribute('skip_464xlat')
        self.add_attribute('user_visible')
        self.add_attribute('user_editable')


def indent(elem, level=0):
    """Based on https://effbot.org/zone/element-lib.htm#prettyprint"""
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# Anything where the value is a package name
unwanted_configs = ["carrier_app_wake_signal_config",
                    "carrier_settings_activity_component_name_string",
                    "carrier_setup_app_string",
                    "config_ims_package_override_string",
                    "enable_apps_string_array",
                    "gps.nfw_proxy_apps",
                    "wfc_emergency_address_carrier_app_string",
                    "ci_action_on_sys_update_bool",
                    "ci_action_on_sys_update_extra_string",
                    "ci_action_on_sys_update_extra_val_string",
                    "ci_action_on_sys_update_intent_string",
                    "allow_adding_apns_bool",
                    "apn_expand_bool",
                    "hide_ims_apn_bool",
                    "hide_preset_apn_details_bool",
                    "read_only_apn_fields_string_array",
                    "read_only_apn_types_string_array",
                    "show_apn_setting_cdma_bool",
                    "carrier_provisioning_app_string",
                    "hide_enable_2g_bool",
                    "com.google.android.dialer.display_wifi_calling_button_bool",
                    "config_ims_rcs_package_override_string"]

unwanted_configs_6thgen = ["smart_forwarding_config_component_name_string"]

qualcomm_pixels = ["crosshatch","blueline","sargo","bonito","barbet","bramble","redfin","sunfish","coral","flame"]

## TODO:
# "carrier_app_wake_signal_config" is still valid on GrapheneOS but we need to implement code for removing "com.google.android.carriersetup" as we don't ship it
# "wfc_emergency_address_carrier_app_string" is still valid on GrapheneOS but we need to remove all values which are not "com.android.imsserviceentitlement/.WfcActivationActivity"


def gen_config_tree(parent, config):
    if config.key in unwanted_configs:
        return
    if (config.key in unwanted_configs_6thgen) and (device not in qualcomm_pixels):
        return
    value_type = config.WhichOneof('value')
    match value_type:
        case 'text_value':
            sub_element = ET.SubElement(parent, 'string')
            sub_element.set('name', config.key)
            sub_element.text = getattr(config, value_type)
        case 'int_value':
            sub_element = ET.SubElement(parent, 'int')
            sub_element.set('name', config.key)
            sub_element.set('value', str(getattr(config, value_type)))
        case 'long_value':
            sub_element = ET.SubElement(parent, 'long')
            sub_element.set('name', config.key)
            sub_element.set('value', str(getattr(config, value_type)))
        case 'bool_value':
            sub_element = ET.SubElement(parent, 'boolean')
            sub_element.set('name', config.key)
            sub_element.set('value', str(getattr(config, value_type)).lower())
        case 'text_array':
            items = getattr(config, value_type).item
            sub_element = ET.SubElement(parent, 'string-array')
            sub_element.set('name', config.key)
            sub_element.set('num', str(len(items)))
            for value in items:
                ET.SubElement(sub_element, 'item').set('value', value)
        case 'int_array':
            items = getattr(config, value_type).item
            sub_element = ET.SubElement(parent, 'int-array')
            sub_element.set('name', config.key)
            sub_element.set('num', str(len(items)))
            for value in items:
                ET.SubElement(sub_element, 'item').set('value', str(value))
        case 'bundle':
            sub_element = ET.SubElement(parent, 'pbundle_as_map')
            sub_element.set('name', config.key)
            configs = getattr(config, value_type).config
            for sub_config in configs:
                gen_config_tree(sub_element, sub_config)
        case 'double_value':
            raise TypeError(f'Found Config value type: {value_type}')
            sub_element = ET.SubElement(parent, 'double')
            sub_element.set('name', config.key)
            sub_element.set('value', str(getattr(config, value_type)))
        case _:
            raise TypeError(f'Unknown Config value type: {value_type}')


carrier_config_root = ET.Element('carrier_config_list')

with open(apn_out, 'w', encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n\n')
    f.write('<apns version="8">\n\n')

    version_suffix = all_settings['default'].version % 1000000000
    for entry in carrier_list.entry:
        setting = all_settings[entry.canonical_name]
        for apn in setting.apns.apn:
            f.write('  <apn carrier={}\n'.format(quoteattr(apn.name)))
            apn_element = ApnElement(apn, entry.carrier_id[0])
            for (key, value) in apn_element.attributes.items():
                f.write('      {}={}\n'.format(escape(key), quoteattr(value)))
            f.write('  />\n\n')

        carrier_config_element = ET.SubElement(
            carrier_config_root,
            'carrier_config',
        )
        carrier_config_element.set('mcc', entry.carrier_id[0].mcc_mnc[:3])
        carrier_config_element.set('mnc', entry.carrier_id[0].mcc_mnc[3:])
        for field in ['spn', 'imsi', 'gid1']:
            if entry.carrier_id[0].HasField(field):
                carrier_config_element.set(
                    field,
                    getattr(entry.carrier_id[0], field),
                )

        # Add version key composed of canonical name and versions
        carrier_config_subelement = ET.SubElement(
            carrier_config_element,
            'string'
        )
        carrier_config_subelement.set('name', 'carrier_config_version_string')
        carrier_config_subelement.text = '{}-{}.{}'.format(
            setting.canonical_name,
            setting.version,
            version_suffix
        )

        for config in setting.configs.config:
            gen_config_tree(carrier_config_element, config)

    f.write('</apns>\n')

indent(carrier_config_root)
carrier_config_tree = ET.ElementTree(carrier_config_root)
root_carrier_config_tree = carrier_config_tree.getroot()

# dict containing lookups for each mccmnc combo representing each file,
# which contains a list of all configs which are dicts
carrier_config_mccmnc_aggregated = {}

for lone_carrier_config in root_carrier_config_tree:
    # append mnc to mcc to form identifier used to lookup carrier XML in CarrierConfig app
    if ("gid1" not in lone_carrier_config.attrib) and ("spn" not in lone_carrier_config.attrib) and ("imsi" not in lone_carrier_config.attrib):
        front = True
    else:
        front = False

    mccmnc_combo = "carrier_config_mccmnc_" + lone_carrier_config.attrib["mcc"] + lone_carrier_config.attrib["mnc"] + ".xml"

    # handle multiple carrier configurations under the same mcc and mnc combination
    if mccmnc_combo not in carrier_config_mccmnc_aggregated:
        blank_list = []
        carrier_config_mccmnc_aggregated[mccmnc_combo] = blank_list
    temp_list = carrier_config_mccmnc_aggregated[mccmnc_combo]
    if front == True:
        temp_list.insert(0,lone_carrier_config)
    else:
        temp_list.append(lone_carrier_config)
    carrier_config_mccmnc_aggregated[mccmnc_combo] = temp_list


with open(cc_out, 'w', encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n')
    f.write('<carrier_config_list>\n')
    for configfile in carrier_config_mccmnc_aggregated:
        config_list = carrier_config_mccmnc_aggregated[configfile]
        for config in config_list:
            config_tree =  ET.ElementTree(config)
            config_tree = config_tree.getroot()
            indent(config_tree)
            single_carrier_config = ET.tostring(config_tree, encoding='unicode')
            single_carrier_config = str(single_carrier_config)
            # workaround for converting wrongfully made no sim config to global defaults for device config
            single_carrier_config = single_carrier_config.replace(' mcc="000" mnc="000"', '')
            f.write(single_carrier_config)
    f.write('</carrier_config_list>\n')
    f.close()

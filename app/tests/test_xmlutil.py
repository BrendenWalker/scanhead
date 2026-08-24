from scanhead.protocol import Target, csv_cmd, msv_value, target_from_status, vol_max_for_model
from scanhead.xmlutil import XmlAssembler, flatten_glt, flatten_menu, flatten_scanner_info, parse_xml, split_frame

GSI = """GSI,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<ScannerInfo Mode="Scan Mode" V_Screen="conventional_scan">\r  <MonitorList Name="Full Database" Index="4294967295" ListType="FullDb" Q_Key="None" N_Tag="None" DB_Counter="0" />\r  <System Name="Department of Justice (DOJ)" Index="25514" Avoid="Off" SystemType="Conventional" Q_Key="None" N_Tag="None" Hold="On" />\r  <Department Name="Public Safety - Radio Plan" Index="25517" Avoid="Off" Q_Key="None" Hold="Off" />\r  <ConvFrequency Name="DOJ-BNE Surveillance" Index="25535" Avoid="Off" Freq=" 155.0400MHz" Mod="NFM" N_Tag="None" Hold="Off" SvcType="Law Tac" P_Ch="Off" SAS="All" SAD="None" RecSlot="Slot None" LVL="0" IFX="Off" TGID="TGID None" U_Id="UID None" />\r  <AGC A_AGC="Off" D_AGC="Off" />\r  <DualWatch PRI="Off" CC="Priority" WX="Off" />\r  <Property F="Off" VOL="3" SQL="11" Sig="0" WiFi="3" Att="Off" Rec="Off" KeyLock="Off" P25Status="None" Mute="Mute" Backlight="0" A_Led="Off" Dir="Up" Rssi="0.403" />\r  <ViewDescription>\r    <InfoArea1 Text="F0:0---------" />\r    <InfoArea2 Text="S0:----------" />\r    <OverWrite Text="Scanning..." />\r  </ViewDescription>\r</ScannerInfo>\r"""

GLT_FL = """GLT,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<GLT>\r  <FL Index="4294967295" Name="Full Database" Monitor="On" Q_Key="None" N_Tag="None" />\r  <FL Index="4261412864" Name="Search with Scan" Monitor="Off" Q_Key="None" N_Tag="None" />\r  <FL Index="0" Name="Reno" Monitor="On" Q_Key="0" N_Tag="0" />\r  <Footer No="1" EOT="1"/>\r</GLT>\r"""

GLT_SYS_1 = """GLT,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<GLT>\r  <SYS Index="104957" Name="National Interagency Fire Center - USA" Avoid="Off" Type="Conventional" />\r  <Footer No="1" EOT="0"/>\r</GLT>\r"""

GLT_SYS_2 = """GLT,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<GLT>\r  <SYS Index="107975" Name="Washoe County Simulcast" Avoid="Off" Type="P25 Trunk" />\r  <Footer No="2" EOT="1"/>\r</GLT>\r"""


def test_split_simple_mdl():
    frame = split_frame(b"MDL,BCD536HP\r")
    assert frame.cmd == "MDL"
    assert frame.fields[1] == "BCD536HP"
    assert not frame.is_xml


def test_split_gsi_xml():
    frame = split_frame(GSI)
    assert frame.cmd == "GSI"
    assert frame.is_xml
    assert "<ScannerInfo" in frame.xml
    root = parse_xml(frame.xml)
    status = flatten_scanner_info(root)
    assert status["mode"] == "Scan Mode"
    assert status["system"]["Name"] == "Department of Justice (DOJ)"
    assert status["channelTag"] == "ConvFrequency"
    assert status["channel"]["Freq"] == " 155.0400MHz"
    assert status["property"]["VOL"] == "3"
    assert status["view"]["overwrite"] == "Scanning..."
    assert status["listen"]["title"] == "DOJ-BNE Surveillance"
    assert status["listen"]["frequency"] == "155.0400MHz"
    assert status["listen"]["scanning"] is True
    assert status["listen"]["landed"] is False


def test_target_from_gsi():
    status = flatten_scanner_info(parse_xml(split_frame(GSI).xml))
    target = target_from_status(status)
    assert target == Target("CFREQ", "25535", "")


def test_glt_single_packet():
    frame = split_frame(GLT_FL)
    assembler = XmlAssembler()
    merged = assembler.add(frame.xml)
    assert merged is not None
    glt = flatten_glt(parse_xml(merged))
    assert glt["kind"] == "FL"
    assert len(glt["items"]) == 3
    assert glt["items"][2]["Name"] == "Reno"


def test_glt_reassembly():
    assembler = XmlAssembler()
    assert assembler.add(split_frame(GLT_SYS_1).xml) is None
    merged = assembler.add(split_frame(GLT_SYS_2).xml)
    assert merged is not None
    glt = flatten_glt(parse_xml(merged))
    assert [item["Index"] for item in glt["items"]] == ["104957", "107975"]


def test_glt_gap_raises():
    assembler = XmlAssembler()
    try:
        assembler.add(split_frame(GLT_SYS_2).xml)
    except ValueError as exc:
        assert "gap" in str(exc)
    else:
        raise AssertionError("expected gap error")


def test_csv_and_msv():
    assert csv_cmd("HLD", "SYS", "1", "") == "HLD,SYS,1,"
    assert msv_value("a,b") == "a\tb"


def test_vol_max():
    assert vol_max_for_model("BCD536HP") == 29
    assert vol_max_for_model("BCD436HP") == 15


ID_SCAN = """PSI,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<ScannerInfo Mode="Trunk Scan" V_Screen="trunk_scan">\r  <System Name="Washoe County" Index="81085" Avoid="Off" SystemType="EDACS" Hold="Off" />\r  <Department Index="4294967295" Avoid="Off" Hold="Off" />\r  <TGID Index="4294967295" Avoid="Off" Hold="Off" />\r  <UnitID />\r  <Site Name="Virginia Peak" Index="81185" Avoid="Off" Hold="Off" Mod="FM" />\r  <SiteFrequency Freq=" 851.3750MHz" IFX="Off" />\r  <Property Mute="Mute" Sig="0" VOL="12" SQL="12" />\r  <ViewDescription>\r    <OverWrite Text="ID Scanning..." />\r  </ViewDescription>\r</ScannerInfo>\r"""

LANDED = """PSI,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<ScannerInfo Mode="Trunk Scan" V_Screen="trunk_scan">\r  <System Name="Nevada Shared Radio System" Index="90505" SystemType="EDACS" Hold="Off" />\r  <Department Name="Nevada DPS - Nevada Highway Patrol" Index="91602" Hold="Off" />\r  <TGID Name="Reno Tac 1 - Reno Metro Area" Index="91712" TGID="TGID:05-145" SvcType="Law Tac" Hold="Off" />\r  <UnitID Name="UID:11748" U_Id="UID:11748" />\r  <Site Name="Reno (Peavine/Red Hill Simulcast)" Index="91043" Mod="FM" Hold="Off" />\r  <SiteFrequency Freq=" 853.2000MHz" />\r  <Property Mute="Unmute" Sig="5" VOL="12" SQL="12" />\r  <ViewDescription>\r    <InfoArea1 Text="F0:0---------" />\r  </ViewDescription>\r</ScannerInfo>\r"""


def test_id_scan_uses_site_frequency():
    status = flatten_scanner_info(parse_xml(split_frame(ID_SCAN).xml))
    listen = status["listen"]
    assert listen["scanning"] is True
    assert listen["landed"] is False
    assert listen["title"] == "Washoe County"
    assert listen["frequency"] == "851.3750MHz"
    assert listen["system"] == "Washoe County"
    assert listen["site"] == "Virginia Peak"
    assert listen["department"] == ""
    assert listen["tgid"] == ""


def test_landed_trunk_channel_details():
    status = flatten_scanner_info(parse_xml(split_frame(LANDED).xml))
    listen = status["listen"]
    assert listen["landed"] is True
    assert listen["scanning"] is False
    assert listen["title"] == "Reno Tac 1 - Reno Metro Area"
    assert listen["tgid"] == "05-145"
    assert listen["frequency"] == "853.2000MHz"
    assert listen["modulation"] == "FM"
    assert listen["service"] == "Law Tac"
    assert listen["unit"] == "11748"
    assert listen["department"] == "Nevada DPS - Nevada Highway Patrol"
    target = target_from_status(status)
    assert target == Target("TGID", "91712", "91602")


def test_id_scan_ignores_placeholder_tgid_index():
    status = flatten_scanner_info(parse_xml(split_frame(ID_SCAN).xml))
    target = target_from_status(status)
    assert target == Target("SITE", "81185", "")


MENU = """MSI,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<Menu Name="TOP" Index="0" MenuType="TypeSelect">\r  <MenuItem Name="Program System" Index="1" />\r  <MenuItem Name="Settings" Index="2" />\r</Menu>\r"""

GLT_FOOT = """GLT,<XML>,\r<?xml version="1.0"?><GLT><FL Index="0" Name="A"/><Foot No="1" EOT="1"/></GLT>\r"""


def test_flatten_menu_select():
    menu = flatten_menu(parse_xml(split_frame(MENU).xml))
    assert menu["name"] == "TOP"
    assert menu["menuType"] == "TypeSelect"
    assert [item["Name"] for item in menu["items"]] == ["Program System", "Settings"]


def test_footer_alias_foot():
    assembler = XmlAssembler()
    merged = assembler.add(split_frame(GLT_FOOT).xml)
    assert merged is not None
    glt = flatten_glt(parse_xml(merged))
    assert glt["items"][0]["Name"] == "A"


def test_frame_ok_and_err():
    assert split_frame(b"KEY,OK\r").ok
    assert split_frame(b"KEY,NG\r").err
    assert not split_frame(b"MDL,BCD536HP\r").err

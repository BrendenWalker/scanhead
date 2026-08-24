from scanhead.protocol import (
    Target,
    csv_cmd,
    key_labels_for_model,
    msv_value,
    sql_max_for_model,
    target_from_status,
    vol_max_for_model,
)


def test_key_labels_sds_relabels_soft_keys():
    labels = key_labels_for_model("SDS200")
    assert labels["A"] == "Soft 1"
    assert labels["E"] == "Yes / Enter"
    assert key_labels_for_model("BCD536HP")["A"] == "System"


def test_level_max_by_model():
    assert vol_max_for_model("BCD536HP") == 29
    assert sql_max_for_model("BCD536HP") == 19
    assert vol_max_for_model("BCD436HP") == 15
    assert sql_max_for_model("UBCD436PT") == 15
    assert sql_max_for_model("") == 19


def test_csv_cmd_and_msv():
    assert csv_cmd("HLD", "SYS", "1", "") == "HLD,SYS,1,"
    assert csv_cmd("PSI", None) == "PSI,"
    assert msv_value("a,b,c") == "a\tb\tc"


def test_target_srch_wx_and_placeholders():
    srch = target_from_status(
        {"channelTag": "SrchFrequency", "channel": {"Freq": " 155.0400MHz"}, "department": {}, "site": {}, "system": {}}
    )
    assert srch == Target("QS_FREQ", "1550400", "")

    wx = target_from_status(
        {"channelTag": "WxChannel", "channel": {"Index": "2"}, "department": {}, "site": {}, "system": {}}
    )
    assert wx == Target("WX", "2", "")

    empty = target_from_status(
        {
            "channelTag": "TGID",
            "channel": {"Index": "4294967295"},
            "department": {"Index": "None"},
            "site": {},
            "system": {},
        }
    )
    assert empty is None

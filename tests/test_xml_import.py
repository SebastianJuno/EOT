from backend.xml_import import parse_tasks_from_project_xml_bytes


XML_SAMPLE = b'''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
  <Tasks>
    <Task>
      <UID>1</UID>
      <Name>Summary</Name>
      <Summary>1</Summary>
      <OutlineLevel>1</OutlineLevel>
      <Start>2026-01-05T08:00:00</Start>
      <Finish>2026-01-10T17:00:00</Finish>
      <Duration>PT40H0M0S</Duration>
    </Task>
    <Task>
      <UID>2</UID>
      <Name>Groundworks</Name>
      <Summary>0</Summary>
      <OutlineLevel>2</OutlineLevel>
      <Start>2026-01-06T08:00:00</Start>
      <Finish>2026-01-09T17:00:00</Finish>
      <Duration>PT24H0M0S</Duration>
      <PercentComplete>50</PercentComplete>
      <BaselineStart>2026-01-06T08:00:00</BaselineStart>
      <BaselineFinish>2026-01-08T17:00:00</BaselineFinish>
      <PredecessorLink>
        <PredecessorUID>1</PredecessorUID>
      </PredecessorLink>
    </Task>
  </Tasks>
</Project>
'''


def test_parse_project_xml_tasks():
    tasks = parse_tasks_from_project_xml_bytes(XML_SAMPLE)
    assert len(tasks) == 2
    assert tasks[1].uid == 2
    assert tasks[1].name == "Groundworks"
    assert tasks[1].duration_minutes == 1440
    assert tasks[1].predecessors == [1]


def test_invalid_xml_raises():
    try:
        parse_tasks_from_project_xml_bytes(b"<not-project>")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Invalid" in str(exc)

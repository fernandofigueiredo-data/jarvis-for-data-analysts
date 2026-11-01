from jarvis.memory import Memory


def test_news_source_filter_is_tolerant(tmp_path):
    m = Memory(tmp_path / "t.db")
    m.add_news("https://www.educadados.com.br/blog/a", "Educadados", "A")
    m.add_news("https://www.datahackers.news/p/b", "Data Hackers", "B")
    for q in ("Educadados", "educadados.com.br", "EducaDados"):
        assert [i["title"] for i in m.latest_news(q)] == ["A"]
    for q in ("Data Hackers", "datahackers", "datahackers.news", "data hackers news"):
        assert [i["title"] for i in m.latest_news(q)] == ["B"]
    assert len(m.latest_news()) == 2

from pathlib import Path

from travel_plan.main import build_workflow


def test_build_workflow_initializes_missing_database(tmp_path):
    root = tmp_path / "workspace"
    (root / "data").mkdir(parents=True)
    (root / "data/seed").symlink_to(Path.cwd() / "data/seed", target_is_directory=True)
    workflow = build_workflow(root, tmp_path / "state")
    assert (root / "data/travel.db").is_file()
    assert len(workflow.facts.all_pois("上海")) == 81

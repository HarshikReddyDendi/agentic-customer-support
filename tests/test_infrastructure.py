import unittest
from pathlib import Path

import yaml


class InfrastructureTests(unittest.TestCase):
    def test_docker_compose_has_api_database_and_streamlit_services(self) -> None:
        compose_path = Path("docker-compose.yml")
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

        self.assertEqual(
            set(compose["services"]),
            {"postgres", "api", "streamlit"},
        )
        self.assertIn("postgres_data", compose["volumes"])
        self.assertIn("faiss_data", compose["volumes"])
        self.assertIn("healthcheck", compose["services"]["postgres"])
        self.assertIn("healthcheck", compose["services"]["api"])

    def test_dockerfile_copies_application_and_frontend(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("COPY app ./app", dockerfile)
        self.assertIn("COPY frontend ./frontend", dockerfile)
        self.assertIn("app.main:app", dockerfile)


if __name__ == "__main__":
    unittest.main()

"""Imports every model module so ``Base.metadata`` describes the full schema
(used by Alembic autogenerate and by tests)."""
from __future__ import annotations

from .domains.discovery import models as discovery_models  # noqa: F401
from .domains.identity import models as identity_models  # noqa: F401
from .domains.organisation import models as organisation_models  # noqa: F401
from .domains.reports import models as reports_models  # noqa: F401
from .domains.systems import models as systems_models  # noqa: F401
from .kernel import audit  # noqa: F401
from .kernel.database import Base

metadata = Base.metadata

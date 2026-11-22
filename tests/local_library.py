"""Where the ``local_library`` tests find this developer's music on disk (#6656).

Those tests are marked ``pytest.mark.local_library`` and run only with
``AURALIS_LOCAL_LIBRARY_TESTS=1`` (#6242, ``tests/conftest.py``); everywhere else the marker skips
them, so they never sniff for a path themselves. Once opted in, a missing file is a failure, not a
skip. The roots are env-overridable for a library mounted elsewhere.
"""

import os
from pathlib import Path

#: The main music collection (artist / album folders).
MUSIC_ROOT = Path(os.environ.get("AURALIS_MUSIC_ROOT", "/mnt/Musica/Musica"))

#: The remasters collection the phase-6 characterisation tests sample.
REMASTERS_ROOT = Path(os.environ.get("AURALIS_REMASTERS_ROOT", "/mnt/audio/Audio/Remasters"))

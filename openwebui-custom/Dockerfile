FROM ghcr.io/open-webui/open-webui:main

COPY custom.js /app/build/static/custom.js

RUN set -eux; \
  for f in /app/build/index.html /app/build/static/index.html /app/build/*/index.html; do \
    if [ -f "$f" ]; then \
      grep -q "custom.js" "$f" || sed -i 's#</body>#<script src="/static/custom.js"></script></body>#' "$f"; \
    fi; \
  done

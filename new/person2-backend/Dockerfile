FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/new/person2-backend
COPY person2-backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY person1-retrieval /srv/new/person1-retrieval
ARG INSTALL_DENSE=false
RUN if [ "$INSTALL_DENSE" = "true" ]; then \
			pip install --no-cache-dir -e "/srv/new/person1-retrieval[dense]"; \
		else \
			pip install --no-cache-dir -e /srv/new/person1-retrieval; \
		fi
COPY contracts /srv/new/contracts
COPY person2-backend /srv/new/person2-backend
RUN useradd --uid 10001 --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM python:3.12

# Must be run as Root user because dumps are not always owned by non-root user.
WORKDIR /core_dump_handler

COPY core_dump_handler /core_dump_handler

RUN pip install -r requirements.txt

ENTRYPOINT [ "/core_dump_handler/entrypoint.sh" ]

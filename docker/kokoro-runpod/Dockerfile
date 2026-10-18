FROM hwdsl2/kokoro-server:cuda

COPY health_bridge.py /opt/runpod/health_bridge.py
COPY start-runpod.sh /opt/runpod/start-runpod.sh

RUN chmod 755 /opt/runpod/start-runpod.sh

EXPOSE 8880/tcp 8888/tcp

CMD ["/opt/runpod/start-runpod.sh"]

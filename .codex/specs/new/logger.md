
Task:
- Setup a logger for the service
- The logger should not log in the compose logs
- It has to log inside a file name "service.log"
- put the looger config in the `user_service/settings.py` file
- modify docker-compose.yml to persist the logs with using volumes
- define the volumes the same way that is defined for database pData directory
- The logger has to:
    - Log errrors
    - Log print() statements output
    - Avoid logging warnings and info 
    - includes time and data

Acceptance Criteria:
- Do not run anything. After the task is done, tell me to test the logger.


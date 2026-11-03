-- 测试库：与开发库隔离，供 `mvn test`（profile=test）使用。
-- 只在 MySQL 容器首次初始化（空数据目录）时执行。
CREATE DATABASE IF NOT EXISTS cs_agent_test CHARACTER SET utf8mb4;
GRANT ALL ON cs_agent_test.* TO 'csagent'@'%';
FLUSH PRIVILEGES;

-- ECG/PCG 平台数据库初始化脚本
-- 创建扩展和基础表结构

-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建枚举类型
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('guest', 'user', 'admin');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE media_type AS ENUM ('audio', 'video', 'ecg', 'pcg');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE annotation_type AS ENUM ('s1', 's2', 'qrs', 'extra_systole', 'murmur', 'artifact', 'other');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE annotation_source AS ENUM ('manual', 'auto');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() NOT NULL UNIQUE,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role user_role DEFAULT 'user' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE NOT NULL,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建项目表
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE NOT NULL,
    is_archived BOOLEAN DEFAULT FALSE NOT NULL,
    recording_date TIMESTAMP WITH TIME ZONE,
    recording_location VARCHAR(255),
    patient_age INTEGER,
    patient_gender VARCHAR(10),
    owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建项目成员表
CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    permission_level VARCHAR(20) DEFAULT 'member' NOT NULL,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (project_id, user_id)
);

-- 创建媒体文件表
CREATE TABLE IF NOT EXISTS media_files (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() NOT NULL UNIQUE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type media_type NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    storage_type VARCHAR(20) DEFAULT 'local' NOT NULL,
    file_size INTEGER NOT NULL,
    duration DOUBLE PRECISION,
    sample_rate INTEGER,
    channels INTEGER,
    resolution VARCHAR(20),
    waveform_data_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    description TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建标记表
CREATE TABLE IF NOT EXISTS annotations (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() NOT NULL UNIQUE,
    annotation_type annotation_type NOT NULL,
    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    label VARCHAR(255),
    description TEXT,
    attributes JSONB,
    source annotation_source DEFAULT 'manual' NOT NULL,
    algorithm_version VARCHAR(50),
    annotated_at TIMESTAMP WITH TIME ZONE,
    file_id INTEGER REFERENCES media_files(id) ON DELETE CASCADE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建工作流表
CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    steps JSONB NOT NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id INTEGER,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_owner_id ON projects(owner_id);
CREATE INDEX idx_projects_is_public ON projects(is_public);
CREATE INDEX idx_projects_is_archived ON projects(is_archived);

CREATE INDEX idx_project_members_user_id ON project_members(user_id);
CREATE INDEX idx_project_members_project_id ON project_members(project_id);
CREATE INDEX idx_project_members_permission ON project_members(permission_level);

CREATE INDEX idx_media_files_project_id ON media_files(project_id);
CREATE INDEX idx_media_files_file_type ON media_files(file_type);
CREATE INDEX idx_media_files_filename ON media_files(filename);
CREATE INDEX idx_media_files_created_at ON media_files(created_at);

CREATE INDEX idx_annotations_file_id ON annotations(file_id);
CREATE INDEX idx_annotations_user_id ON annotations(user_id);
CREATE INDEX idx_annotations_type ON annotations(annotation_type);
CREATE INDEX idx_annotations_source ON annotations(source);
CREATE INDEX idx_annotations_start_time ON annotations(start_time);
CREATE INDEX idx_annotations_created_at ON annotations(created_at);

CREATE INDEX idx_workflows_project_id ON workflows(project_id);
CREATE INDEX idx_workflows_created_by ON workflows(created_by);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- 创建函数和触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为表添加更新触发器
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_annotations_updated_at BEFORE UPDATE ON annotations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 插入默认数据
INSERT INTO users (
    username, 
    email, 
    password_hash, 
    full_name, 
    role,
    is_active,
    is_verified
) VALUES 
    (
        'admin',
        'admin@example.com',
        -- 密码: Admin123! (bcrypt哈希)
        '$2b$12$7K1y8VYQcLzg6Nq7Q1WZ8O/.eJtL7v1kY9M6V3qL2aN1bC5d8E7fG',
        '系统管理员',
        'admin',
        TRUE,
        TRUE
    ),
    (
        'testuser',
        'user@example.com',
        -- 密码: Test123!
        '$2b$12$7K1y8VYQcLzg6Nq7Q1WZ8O/.eJtL7v1kY9M6V3qL2aN1bC5d8E7fG',
        '测试用户',
        'user',
        TRUE,
        TRUE
    )
ON CONFLICT (username) DO NOTHING;

-- 创建测试项目
INSERT INTO projects (
    name,
    description,
    is_public,
    owner_id
) 
SELECT 
    '示例心音研究项目',
    '这是一个示例项目，用于演示ECG/PCG平台的功能。包含多个心音和心电数据样本。',
    TRUE,
    id
FROM users WHERE username = 'admin'
ON CONFLICT DO NOTHING;

-- 添加测试用户到项目
INSERT INTO project_members (project_id, user_id, permission_level)
SELECT 
    p.id,
    u.id,
    'member'
FROM projects p, users u 
WHERE p.name = '示例心音研究项目' 
    AND u.username = 'testuser'
ON CONFLICT DO NOTHING;

-- 注释表空间建议
COMMENT ON TABLE users IS '系统用户表，包含认证和权限信息';
COMMENT ON TABLE projects IS '研究项目管理表';
COMMENT ON TABLE project_members IS '项目成员关系表';
COMMENT ON TABLE media_files IS '媒体文件存储表（音频/视频/ECG/PCG）';
COMMENT ON TABLE annotations IS '数据标记表';
COMMENT ON TABLE workflows IS '数据分析工作流表';
COMMENT ON TABLE audit_logs IS '系统审计日志表';

-- 输出成功信息
DO $$ BEGIN
    RAISE NOTICE 'ECG/PCG平台数据库初始化完成！';
    RAISE NOTICE '默认用户: admin / Admin123!';
    RAISE NOTICE '测试用户: testuser / Test123!';
END $$;
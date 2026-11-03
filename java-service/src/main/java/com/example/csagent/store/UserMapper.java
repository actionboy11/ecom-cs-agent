package com.example.csagent.store;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.csagent.domain.UserEntity;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper extends BaseMapper<UserEntity> {
}

package com.example.csagent.store;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.csagent.domain.OrderEntity;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderMapper extends BaseMapper<OrderEntity> {
}

package com.example.csagent.domain;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import java.time.LocalDateTime;

@TableName("logistics_traces")
public class LogisticsTraceEntity {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String orderNo;
    private Integer seq;
    private LocalDateTime traceTime;
    private String content;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getOrderNo() {
        return orderNo;
    }

    public void setOrderNo(String orderNo) {
        this.orderNo = orderNo;
    }

    public Integer getSeq() {
        return seq;
    }

    public void setSeq(Integer seq) {
        this.seq = seq;
    }

    public LocalDateTime getTraceTime() {
        return traceTime;
    }

    public void setTraceTime(LocalDateTime traceTime) {
        this.traceTime = traceTime;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }
}

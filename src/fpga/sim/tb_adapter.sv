`timescale 1ns/1ps
module tb_adapter;
 reg clk=0;always #10 clk=~clk;
 reg rst=1,valid=0,ready_rsp=0;reg [19:0] addr=0;reg [2:0] size=1;reg [31:0] job=4;
 wire ready,rv,error,re,empty;wire [31:0] data,rjob,q;wire [19:0] ra;
 reg we=0;reg [19:0] wa=0;reg [31:0] wd=0;
 wire [7:0] aq,wq;wire [31:0] bq,mq,sq,gm,gs;
 stage5_adapter dut(clk,rst,1'b1,valid,ready,addr,size,job,rv,ready_rsp,data,rjob,error,re,ra,q,empty);
 stage5_memory ram(clk,rst,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,15'd0,15'd0,15'd0,7'd0,7'd0,16'd0,8'd0,8'd0,32'd0,10'd0,aq,wq,bq,mq,sq,re,we,ra,wa,wd,q,1'b0,9'd0,32'd0,gm,gs);
 integer f,i,edge_no=0;
 always @(posedge clk)begin edge_no=edge_no+1;$fdisplay(f,"%0d,%b,%b,%b,%h,%b,%h,%b,%b",edge_no,rst,valid,ready,addr,re,data,rv,ready_rsp);end
 task tick;begin @(posedge clk);#1;end endtask
 task write_word(input [19:0] a,input [31:0] d);begin @(negedge clk);we=1;wa=a;wd=d;tick();@(negedge clk);we=0;end endtask
 task read_word(input [19:0] a,input [2:0] n,input [31:0] expected);
 begin @(negedge clk);addr=a;size=n;valid=1;tick();if(rv)$fatal(1,"early E response");@(negedge clk);valid=0;
 tick();if(rv)$fatal(1,"early E1 response");tick();if(!rv||data!==expected||rjob!=4)$fatal(1,"E2 response %h expected %h",data,expected);
 repeat(4)begin tick();if(!rv||data!==expected)$fatal(1,"stall unstable");end
 @(negedge clk);ready_rsp=1;tick();@(negedge clk);ready_rsp=0;if(!empty)$fatal(1,"drain");end endtask
 initial begin
 f=$fopen("adapter_trace.csv","w");repeat(8)tick();@(negedge clk);rst=0;
 write_word(20'h38c3f,32'h7e);write_word(20'h40390,32'h89abcdef);write_word(20'h41390,32'h12345678);
 read_word(20'h38c3f,1,32'h7e);read_word(20'h40390,4,32'h89abcdef);read_word(20'h40393,1,32'h89);read_word(20'h41390,4,32'h12345678);
 for(i=0;i<4;i=i+1)begin
 @(negedge clk);valid=1;addr='h40390;size=4;tick();@(negedge clk);valid=0;repeat(i)tick();@(negedge clk);rst=1;tick();if(rv||re)$fatal(1,"reset flush");@(negedge clk);rst=0;tick();if(rv||!empty)$fatal(1,"stale return");end
 read_word(20'h40390,4,32'h89abcdef);
 $fclose(f);$display("TB COMPLETE adapter cases=9");$finish;
 end
 initial begin #100000;$fatal(1,"watchdog");end
endmodule

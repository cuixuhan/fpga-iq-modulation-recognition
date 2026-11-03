`timescale 1ns/1ps
module tb_network;
 reg clk=0;always #10 clk=~clk;
 reg reset_n=0,fv=0,fw=0,rr=0,sent=0;wire fr,rv;reg [31:0] a;reg [15:0] n;reg [2047:0] d;wire [2047:0] rd;wire [7:0] error;wire [15:0] rn;
 stage5_top dut(clk,reset_n,fv,fr,fw,a,n,d,rv,rr,sent,error,rn,rd);
 reg [7:0] load_a[0:2047],load_w[0:35903],load_b[0:915],load_m[0:915],load_s[0:915],load_g[0:7];
 integer f,tr,i,j,r,sz,off,count;reg [31:0] addr;reg [2047:0] response;
 task transaction(input bit wr,input [31:0] address,input integer len,input [2047:0] data,input [7:0] expected_error);
 begin
 @(negedge clk);while(!fr)@(negedge clk);fw=wr;a=address;n=len;d=data;fv=1;
 @(negedge clk);fv=0;while(!rv)@(negedge clk);
 if(error!==expected_error)$fatal(1,"transaction addr=%h error=%d expected=%d",address,error,expected_error);
 response=rd;rr=1;@(negedge clk);rr=0;sent=1;@(negedge clk);sent=0;
 end endtask
 task dump(input integer st,input [31:0] address,input integer bytes,input integer kind);
 integer o,l,k;begin
 for(o=0;o<bytes;o=o+256)begin l=bytes-o>256?256:bytes-o;transaction(0,address+o,l,0,0);
 for(k=0;k<l;k=k+1)$fdisplay(f,"R,%0d,%0d,%0d,%0d",st,kind,o+k,response[k*8+:8]);
 end end endtask
 always @(posedge clk)if(!dut.pipeline_rst)begin
 if(dut.cwv&&dut.co)$fdisplay(f,"C,%0d,%0d,%0d,%0d",dut.stage,dut.cba,$signed(dut.cdata),$signed(dut.cacc));
 if(dut.wv&&dut.po)$fdisplay(f,"P,%0d,%0d,%0d,0",dut.stage,dut.waddr,$signed(dut.wdata));
 if(dut.ov&&dut.po)$fdisplay(f,"O,%0d,%0d,%0d,0",dut.stage,dut.oi,$signed(dut.oacc));
 if(dut.cs||dut.ps||dut.cdone||dut.pdone||dut.flush)$fdisplay(tr,"%0t stage=%0d state=%0d cs=%b ps=%b cd=%b pd=%b flush=%b",$time,dut.stage,dut.state,dut.cs,dut.ps,dut.cdone,dut.pdone,dut.flush);
 end
 initial begin
 f=$fopen("network_actual.csv","w");tr=$fopen("network_trace.txt","w");
 $readmemh("vectors/A.mem",load_a);$readmemh("vectors/W.mem",load_w);$readmemh("vectors/bias.mem",load_b);$readmemh("vectors/M.mem",load_m);$readmemh("vectors/shift.mem",load_s);$readmemh("vectors/gap.mem",load_g);
 repeat(5)@(negedge clk);reset_n=1;repeat(5)@(negedge clk);
 transaction(0,0,4,0,0);if(response[31:0]!=32'h50003)$fatal(1,"version");
 transaction(1,4,1,1,3);transaction(1,256,4,32'h53000001,0);transaction(1,320,8,64'h1122334455667788,0);transaction(1,260,4,1,0);
 for(r=0;r<6;r=r+1)begin
 case(r)0:begin addr='h10000;sz=2048;end 1:begin addr='h30000;sz=35904;end 2:begin addr='h40000;sz=916;end 3:begin addr='h41000;sz=916;end 4:begin addr='h42000;sz=916;end 5:begin addr='h43000;sz=8;end endcase
 for(off=0;off<sz;off=off+256)begin count=sz-off>256?256:sz-off;d=0;
 for(j=0;j<count;j=j+1)case(r)0:d[j*8+:8]=load_a[off+j];1:d[j*8+:8]=load_w[off+j];2:d[j*8+:8]=load_b[off+j];3:d[j*8+:8]=load_m[off+j];4:d[j*8+:8]=load_s[off+j];5:d[j*8+:8]=load_g[off+j];endcase
 transaction(1,addr+off,count,d,0);end end
 transaction(1,256,4,32'h53000002,0);
 transaction(1,256,4,32'h53000002,1);
 for(i=0;i<8;i=i+1)begin
 wait(dut.state==5||dut.state==7);if(dut.state==7)$fatal(1,"network fatal stage=%0d code=%0d",dut.stage,dut.ctl_error);
 $display("STAGE_PAUSED %0d cycles=%0d",i,dut.cycles);
 if(dut.stage!=i)$fatal(1,"stage ordering");
 case(i)
 0,2,4:begin dump(i,'h20000,32768,0);dump(i,'h50000,2048,1);end
 1,3:dump(i,'h10000,16384,0);
 5:begin dump(i,'h10000,128,0);dump(i,'h50000,512,1);end
 6:begin dump(i,'h20000,5,0);dump(i,'h50200,20,1);end
 7:begin dump(i,80,4,0);end
 endcase
 transaction(1,264,16,{dut.token,dut.job,64'h1122334455667788},0);
 transaction(1,256,4,32'h53000003,0);
 wait(dut.state!=5);
 end
 wait(dut.state==6);if(!dut.output_valid||dut.ns!=1||dut.vs!=3||dut.os!=5)$fatal(1,"completion counts");
 transaction(0,'h20000,5,0,0);$display("LOGITS packed=%h",response[39:0]);
 @(negedge clk);reset_n=0;repeat(5)@(negedge clk);reset_n=1;repeat(5)@(negedge clk);
 transaction(0,'h20000,5,0,6);
 $fclose(f);$fclose(tr);$display("TB COMPLETE network stages=8");$finish;
 end
 initial begin repeat(1000)#20000000;$fatal(1,"watchdog");end
endmodule

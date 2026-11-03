// Fork of cnn_dense_core: production arithmetic and scanner, external shared RAM.
module stage5_dense_core(input wire clk,rst,start,
 input wire [15:0] cin,cout,len,input wire [7:0] kernel,pad,
 input wire signed [7:0] zx,zy,input wire relu,input wire [7:0] job_id,
 input wire [7:0] aq,wq,input wire [31:0] biasq,mq,shiftq,
 input wire write_ready,output reg busy,done,output_valid,output reg [7:0] error_code,
 output wire a_read,w_read,bias_read,params_read,write_valid,
 output wire [14:0] a_address,w_address,b_address,
 output wire [6:0] bias_address,param_address,
 output wire [7:0] b_data,output wire [31:0] debug_acc,
 output wire [9:0] debug_index);
 wire [15:0] lout=len+{8'd0,pad}*2-{8'd0,kernel}+1;
 wire [15:0] output_size=cout*lout;
 wire pipe_reset=rst||!busy;
 reg [63:0] cycles,scanned,issued_macs,committed;
 reg counter_overflow;reg [9:0] debug_count;
 // Conservative scanner: at most one fixed-latency read in flight. It reserves
 // candidate credit before RAM issue, so occupancy + inflight never exceeds 64.
 localparam S_IDLE=0,S_BIAS=1,S_INIT=2,S_READ=3,S_RETURN=4,S_PUSH=5,
  S_CONSUME=6,S_NEXT=7,S_FINISH=8,S_RESULT=9,S_ADV=10;
 reg [3:0] ss;
 reg [6:0] oc;reg [9:0] pos;reg [5:0] ci;reg [2:0] ki;
 reg scan_finished;reg [63:0] candidate;
 wire signed [16:0] xpos=$signed({7'd0,pos})+$signed({14'd0,ki})-$signed({9'd0,pad});
 wire padding=xpos<0||xpos>=$signed({1'b0,len});
 wire last_candidate=({10'd0,ci}+1==cin)&&({5'd0,ki}+1==kernel);
 wire last_output=({9'd0,oc}+1==cout)&&({6'd0,pos}+1==lout);
 wire [14:0] a_addr=ci*len+xpos;
 wire cf_ir,cf_ov,rf_ir,rf_ov;wire [63:0] cf_od,rf_od;wire [6:0] cf_occ,rf_occ;
 wire [14:0] w_addr=(cf_od[33:27]*cin+cf_od[13:8])*kernel+cf_od[16:14];
 wire cf_iv=busy&&ss==S_PUSH;
 wire cf_pop=busy&&ss==S_CONSUME;
 dense_fifo candidates(clk,pipe_reset,cf_iv,cf_ir,candidate,cf_ov,cf_pop,cf_od,cf_occ);
 wire mem_issue=busy&&ss==S_READ&&cf_ir;

 wire bias_init=busy&&ss==S_INIT;
 wire mac_ready,mac_valid,mac_overflow;wire signed [31:0] mac_acc;
 wire weight_read=cf_ov&&cf_pop&&!cf_od[35];
 wire mac_step=busy&&ss==S_NEXT&&!cf_od[35];
 wire rf_iv=busy&&ss==S_RESULT&&mac_valid;
 wire [63:0] rf_id={6'd0,last_output,job_id,cf_od[26:17],cf_od[33:27],mac_acc};
 pe_mac mac(clk,pipe_reset,bias_init,$signed(biasq),mac_step,$signed(cf_od[7:0]),zx,
  $signed(wq),busy&&ss==S_FINISH,mac_ready,mac_valid,rf_ir&&rf_iv,mac_acc,mac_overflow);
 reg [1:0] rs;reg [63:0] result_tag;
 wire rf_pop=busy&&rs==0;
 dense_fifo results(clk,pipe_reset,rf_iv,rf_ir,rf_id,rf_ov,rf_pop,rf_od,rf_occ);
 wire param_read=rf_ov&&rf_pop;
 wire rq_ir,rq_ov,rq_error;wire signed [7:0] rq_data;
 wire b_ready=write_ready;
 wire b_valid=busy&&rs==2&&rq_ov&&!rq_error;
 wire b_commit=b_valid&&b_ready;
 wire [14:0] b_addr=result_tag[38:32]*lout+result_tag[48:39];
 requant_even requant(clk,pipe_reset,busy&&rs==1,rq_ir,$signed(result_tag[31:0]),
  $signed(mq),shiftq,zy,relu,rq_ov,b_ready&&rs==2,rq_data,rq_error);

 assign a_read=mem_issue&&!padding&&!rst;assign a_address=a_addr;
 assign w_read=weight_read&&!rst;assign w_address=w_addr;
 assign bias_read=busy&&ss==S_BIAS&&!rst;assign bias_address=oc;
 assign params_read=param_read&&!rst;assign param_address=rf_od[38:32];
 assign write_valid=b_valid&&!rst;assign b_address=b_addr;assign b_data=rq_data;
 assign debug_acc=result_tag[31:0];assign debug_index=debug_count;
 function [63:0] inc64(input [63:0] v);inc64=(&v)?v:v+1;endfunction
 always @(posedge clk) begin
  if(rst)begin
   busy<=0;done<=0;output_valid<=0;error_code<=0;
   cycles<=0;scanned<=0;issued_macs<=0;committed<=0;counter_overflow<=0;debug_count<=0;
   ss<=S_IDLE;rs<=0;oc<=0;pos<=0;ci<=0;ki<=0;scan_finished<=0;candidate<=0;result_tag<=0;
  end else begin
   done<=0;
   if(start&&!busy)begin
    busy<=1;output_valid<=0;error_code<=0;cycles<=0;scanned<=0;issued_macs<=0;committed<=0;
    counter_overflow<=0;debug_count<=0;ss<=S_BIAS;rs<=0;oc<=0;pos<=0;ci<=0;ki<=0;scan_finished<=0;
   end
   if(busy)begin
    cycles<=inc64(cycles);
    if(&cycles)counter_overflow<=1;
    case(ss)
     S_BIAS:ss<=S_INIT;
     S_INIT:ss<=S_READ;
     S_READ:if(cf_ir)begin
      candidate<={28'd0,padding,last_candidate,oc,pos,ki,ci,zx};
      scanned<=inc64(scanned);if(&scanned)counter_overflow<=1;
      ss<=S_RETURN;
     end
     S_RETURN:begin
      if(!candidate[35])candidate[7:0]<=aq;
      ss<=S_PUSH;
     end
     S_PUSH:if(cf_ir)ss<=S_CONSUME;
     S_CONSUME:if(cf_ov)begin
      ss<=S_NEXT;
     end
     S_NEXT:begin
      if(!cf_od[35])begin issued_macs<=inc64(issued_macs);if(&issued_macs)counter_overflow<=1;end
      if(cf_od[34])ss<=S_FINISH;
      else begin
       if({5'd0,cf_od[16:14]}+1==kernel)begin ki<=0;ci<=cf_od[13:8]+1;end else ki<=cf_od[16:14]+1;
       ss<=S_READ;
      end
     end
     S_FINISH:ss<=S_RESULT;
     S_RESULT:if(rf_iv&&rf_ir)ss<=S_ADV;
     S_ADV:if(last_output)begin scan_finished<=1;ss<=S_IDLE;end
      else begin
       if({6'd0,pos}+1==lout)begin pos<=0;oc<=oc+1;end else pos<=pos+1;
       ci<=0;ki<=0;ss<=S_BIAS;
      end
    endcase
    if(param_read)begin result_tag<=rf_od;rs<=1;end
    if(rs==1&&rq_ir)rs<=2;
    if(b_commit)begin
     rs<=0;committed<=inc64(committed);if(&committed)counter_overflow<=1;
     if(debug_count<512)debug_count<=debug_count+1;
     if(result_tag[57]&&scan_finished&&cf_occ==0&&rf_occ==0&&committed+1==output_size)begin
      done<=1;busy<=0;output_valid<=1;
     end
    end
    if(mac_overflow||(rq_ov&&rq_error)||(busy&&rs==2&&result_tag[56:49]!=job_id))begin
     busy<=0;done<=0;output_valid<=0;ss<=S_IDLE;rs<=0;error_code<=7;
    end
   end
  end
 end
endmodule

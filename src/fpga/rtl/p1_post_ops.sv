// DRAFT p1-day2-v1. Linear is a standalone serial CANDIDATE, not a route decision.
// One outstanding read. wr_ready means physical commit. job IDs MUST NOT be reused
// while stale responses can exist; person2 must flush adapter on reset or enforce this.
module p1_post_ops(
 input wire clk,rst,start,clear_error,params_valid, input wire [1:0] op,
 input wire [31:0] job_id,input wire [15:0] channels,length,
 input wire [19:0] src_base,dst_base,w_base,bias_base,m_base,shift_base,
 input wire signed [7:0] zx,zy,input wire signed [31:0] gap_m,input wire [31:0] gap_shift,
 output wire start_ready,busy,output reg done,output_valid,error_valid,
 output reg [7:0] error_code,output reg [31:0] active_job,
 output wire rd_valid,input wire rd_ready,output reg [19:0] rd_addr,
 output reg [2:0] rd_bytes,output wire [31:0] rd_job,
 input wire rd_rsp_valid,output wire rd_rsp_ready,input wire [31:0] rd_data,rd_rsp_job,
 input wire rd_error,output wire wr_valid,input wire wr_ready,
 output wire [19:0] wr_addr,output reg signed [7:0] wr_data,
 output wire obs_valid,input wire obs_ready,output wire [31:0] obs_job,
 output wire [15:0] obs_index,output wire [1:0] obs_kind,
 output wire signed [31:0] obs_acc,
 output reg winner_valid,output reg [2:0] winner_index,output reg signed [7:0] winner_value
);
 localparam IDLE=0,REQ=1,DELAY=2,WAIT_RSP=3,QUANT=4,OBS=5,WRITE=6,FINISH=7;
 localparam DATA=0,BIAS=1,MULT=2,SHIFT=3,WEIGHT=4;
 reg [3:0] state;reg [2:0] purpose;reg [1:0] mode,delay_count;
 reg [19:0] src,dst,weights,biases,mults,shifts;
 reg signed [7:0] z_x,z_y,left,x;
 reg signed [31:0] acc,m;reg [31:0] s;
 reg [15:0] out_index,item;reg [15:0] out_count;
 reg signed [7:0] best;reg [2:0] best_index;
 wire signed [8:0] centered=$signed({rd_data[7],rd_data[7:0]})-$signed({z_x[7],z_x});
 wire signed [8:0] xcenter=$signed({x[7],x})-$signed({z_x[7],z_x});
 wire signed [16:0] prod=xcenter*$signed(rd_data[7:0]);
 wire signed [32:0] sum_gap=$signed({acc[31],acc})+$signed({{24{centered[8]}},centered});
 wire signed [32:0] sum_mac=$signed({acc[31],acc})+$signed({{16{prod[16]}},prod});
 wire signed [63:0] rq_product,rq_rounded;wire signed [64:0] rq_raw;
 wire signed [7:0] rq_value;wire rq_illegal;
 p1_requant rq(acc,m,s,z_y,rq_product,rq_rounded,rq_raw,rq_value,rq_illegal);
 assign busy=state!=IDLE;assign start_ready=!busy&&!rst;
 assign rd_valid=state==REQ&&!rst;assign rd_job=active_job;
 // Drain foreign-tag responses without consuming them as operands.
 assign rd_rsp_ready=!rst && ((rd_rsp_job!=active_job)||state==WAIT_RSP||state==IDLE);
 assign wr_valid=state==WRITE&&!rst;assign wr_addr=dst+out_index;
 assign obs_valid=state==OBS&&!rst;assign obs_job=active_job;
 assign obs_index=out_index;assign obs_kind=mode==1 ? 0:1;assign obs_acc=acc;
 wire legal_shape=(op==0 && ((channels==32&&length==1024)||(channels==64&&length==512))) ||
 (op==1&&channels==128&&length==256)||(op==2&&channels==128&&length==1)||(op==3&&channels==5&&length==1);
 wire legal_addr=({1'b0,src_base}+(op<2?21'd32767:op==2?21'd127:21'd4)<=21'hfffff)&&
 ({1'b0,dst_base}+(op==0?21'd16383:op==1?21'd127:21'd4)<=21'hfffff)&&
 (op!=2 || (({1'b0,w_base}+639<=21'hfffff)&&({1'b0,bias_base}+19<=21'hfffff)&&
 ({1'b0,m_base}+19<=21'hfffff)&&({1'b0,shift_base}+19<=21'hfffff)&&
 bias_base[1:0]==0&&m_base[1:0]==0&&shift_base[1:0]==0));
 task fatal_job(input [7:0] code);begin
 state<=IDLE;error_valid<=1;error_code<=code;output_valid<=0;winner_valid<=0;
 end endtask
 task request(input [19:0] address,input [2:0] bytes,input [2:0] why);begin
 rd_addr<=address;rd_bytes<=bytes;purpose<=why;state<=REQ;
 end endtask
 always @(posedge clk) begin
  if(rst) begin
   state<=IDLE;done<=0;output_valid<=0;error_valid<=0;error_code<=0;active_job<=0;
   winner_valid<=0;winner_index<=0;winner_value<=0;rd_addr<=0;rd_bytes<=0;wr_data<=0;
   purpose<=0;mode<=0;delay_count<=0;src<=0;dst<=0;weights<=0;biases<=0;mults<=0;shifts<=0;
   z_x<=0;z_y<=0;left<=0;x<=0;acc<=0;m<=0;s<=0;out_index<=0;item<=0;out_count<=0;best<=0;best_index<=0;
  end else begin
   done<=0;
   if(clear_error&&!busy)begin error_valid<=0;error_code<=0;end
   if(start&&busy)begin error_valid<=1;error_code<=1;end
   case(state)
    IDLE:if(start)begin
     output_valid<=0;winner_valid<=0;active_job<=job_id;
     if(!legal_shape||!legal_addr)fatal_job(2);
     else if(!params_valid||(op==1&&(gap_m<=0||gap_shift>62)))fatal_job(3);
     else begin
      mode<=op;src<=src_base;dst<=dst_base;weights<=w_base;biases<=bias_base;mults<=m_base;shifts<=shift_base;
      z_x<=zx;z_y<=zy;m<=gap_m;s<=gap_shift;acc<=0;item<=0;out_index<=0;
      out_count<=op==0?16384:op==1?128:5;best<=-128;best_index<=0;
      if(op==2)request(bias_base,4,BIAS);else request(src_base,1,DATA);
     end
    end
    REQ:if(rd_ready)begin state<=DELAY;delay_count<=0;end
    DELAY:if(delay_count==1)state<=WAIT_RSP;else delay_count<=delay_count+1;
    WAIT_RSP:if(rd_rsp_valid&&rd_rsp_job==active_job)begin
     if(rd_error)fatal_job(4);
     else case(purpose)
      BIAS:begin acc<=$signed(rd_data);request(mults+4*out_index,4,MULT);end
      MULT:if($signed(rd_data)<=0)fatal_job(3);else begin m<=$signed(rd_data);request(shifts+4*out_index,4,SHIFT);end
      SHIFT:if(rd_data>62)fatal_job(3);else begin s<=rd_data;request(src,1,DATA);end
      WEIGHT:if($signed(rd_data[7:0])==-128)fatal_job(3);
       else if(sum_mac[32]!=sum_mac[31])fatal_job(5);
       else begin
        acc<=sum_mac[31:0];
        if(item==127)state<=QUANT;
        else begin item<=item+1;request(src+item+1,1,DATA);end
       end
      DATA:case(mode)
       0:if(!item[0])begin left<=$signed(rd_data[7:0]);item<=1;request(src+2*out_index+1,1,DATA);end
         else begin wr_data<=left>$signed(rd_data[7:0])?left:$signed(rd_data[7:0]);state<=WRITE;end
       1:if(sum_gap[32]!=sum_gap[31])fatal_job(5);else begin
         acc<=sum_gap[31:0];if(item==255)state<=QUANT;
         else begin item<=item+1;request(src+256*out_index+item+1,1,DATA);end
        end
       2:begin x<=$signed(rd_data[7:0]);request(weights+128*out_index+item,1,WEIGHT);end
       3:begin
         if(item==0||$signed(rd_data[7:0])>best)begin best<=$signed(rd_data[7:0]);best_index<=item[2:0];end
         if(item==4)state<=FINISH;else begin item<=item+1;request(src+item+1,1,DATA);end
        end
      endcase
     endcase
    end
    QUANT:if(rq_illegal)fatal_job(3);else begin wr_data<=rq_value;state<=OBS;end
    OBS:if(obs_ready)state<=WRITE;
    WRITE:if(wr_ready)begin
     if(out_index==out_count-1)state<=FINISH;
     else begin
      out_index<=out_index+1;item<=0;acc<=0;
      if(mode==0)request(src+2*(out_index+1),1,DATA);
      else if(mode==1)request(src+256*(out_index+1),1,DATA);
      else request(biases+4*(out_index+1),4,BIAS);
     end
    end
    FINISH:begin
     done<=1;output_valid<=1;state<=IDLE;
     if(mode==3)begin winner_valid<=1;winner_index<=best_index;winner_value<=best;end
    end
    default:fatal_job(6);
   endcase
  end
 end
endmodule

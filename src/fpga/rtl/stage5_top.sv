// Complete-frame endpoint. stage5_wire_top supplies the real CRC byte bridge.
module stage5_top(input wire clk,reset_n,
 input wire frame_valid,output wire frame_ready,input wire frame_write,
 input wire [31:0] frame_addr,input wire [15:0] frame_len,input wire [2047:0] frame_data,
 output reg reply_valid,input wire reply_ready,input wire reply_sent,
 output reg [7:0] reply_error,output reg [15:0] reply_len,output reg [2047:0] reply_data);
 (* ASYNC_REG="TRUE" *) reg [1:0] reset_sync;
 always @(posedge clk or negedge reset_n)if(!reset_n)reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
 wire rst=!reset_sync[1];
 reg begin_load,start,resume,abort_job,clear_error,diag;
 reg [63:0] session;reg [127:0] resume_context;reg context_valid;
 wire [2:0] stage;wire [3:0] state;wire co,po,cs,ps,flush,output_valid;
 wire [7:0] ctl_error;wire [31:0] job,token;wire [63:0] ns,vs,os,cycles,pauses;
 reg [31:0] loaded_count[0:5];reg [23:0] partial[0:3];
 reg [31:0] diag_output,diag_acc;wire [31:0] required_output=(stage==0||stage==2||stage==4)?32768:(stage==1||stage==3)?16384:stage==5?128:stage==6?5:4;
 wire [31:0] required_acc=(stage==0||stage==2||stage==4)?2048:stage==5?512:stage==6?20:0;
 wire all_loaded=loaded_count[0]==2048&&loaded_count[1]==35904&&loaded_count[2]==916&&loaded_count[3]==916&&loaded_count[4]==916&&loaded_count[5]==8;
 wire [7:0] ce,pe;wire cb,cdone,pb,pdone,pvalid,perr,pwinner;
 wire [2:0] winner;wire signed [7:0] winner_value;
 wire adapter_empty,arsp;wire [31:0] adata,ajob;wire aerr;
 wire pipeline_rst=rst||flush||state==7;
 stage5_control control(clk,rst,begin_load,start,all_loaded,session!=0,diag,resume,
 context_valid&&resume_context=={token,job,session},diag_output==required_output&&diag_acc==required_acc,
 abort_job,co?cdone:pdone,adapter_empty&&!cb&&!pb,co?ce:(perr?(pe==5?8'd7:8'd2):8'd0),
 stage,state,co,po,cs,ps,flush,output_valid,ctl_error,job,token,ns,vs,os,cycles,pauses);
 wire [15:0] cin=stage==0?16'd2:stage==2?16'd32:16'd64;
 wire [15:0] cout=stage==0?16'd32:stage==2?16'd64:16'd128;
 wire [15:0] length=stage==0?16'd1024:stage==2?16'd512:16'd256;
 wire [7:0] kernel=stage==0?8'd7:stage==2?8'd5:8'd3,pad=stage==0?8'd3:stage==2?8'd2:8'd1;
 wire [15:0] wb=stage==0?16'd0:stage==2?16'd448:16'd10688;
 wire [7:0] pbase=stage==0?8'd0:stage==2?8'd32:8'd96;
 wire car,cwr,cbr,cpr,cwv;wire [14:0] caa,cwa,cba;wire [6:0] cbi,cpi;
 wire [7:0] cdata,aq,wq;wire [31:0] cacc,bq,mq,sq;wire [9:0] cindex;
 wire cvout;
 stage5_dense_core conv(clk,pipeline_rst,cs,cin,cout,length,kernel,pad,
 stage==0?-8'sd4:-8'sd128,-8'sd128,1'b1,job[7:0],aq,wq,bq,mq,sq,1'b1,cb,cdone,cvout,ce,
 car,cwr,cbr,cpr,cwv,caa,cwa,cba,cbi,cpi,cdata,cacc,cindex);
 wire rdv,rdr,rrdy,wv,ov;wire [19:0] raddr,waddr;wire [2:0] rbytes;wire [31:0] rjob,active_job,ojob;wire signed [7:0] wdata;wire [15:0] oi;wire [1:0] okind;wire signed [31:0] oacc;
 wire signed [31:0] gap_m;wire [31:0] gap_shift;
 wire [1:0] op=stage==1||stage==3?2'd0:stage==5?2'd1:stage==6?2'd2:2'd3;
 wire [15:0] channels=stage==1?16'd32:stage==3?16'd64:stage==7?16'd5:16'd128;
 wire [15:0] plen=stage==1?16'd1024:stage==3?16'd512:stage==5?16'd256:16'd1;
 p1_post_ops post(.clk(clk),.rst(pipeline_rst),.start(ps),.clear_error(clear_error),.params_valid(all_loaded),.op(op),.job_id(job),.channels(channels),.length(plen),
 .src_base(stage==6?20'h10000:20'h20000),.dst_base(stage==6?20'h20000:20'h10000),.w_base(20'h389c0),.bias_base(20'h40380),.m_base(20'h41380),.shift_base(20'h42380),
 .zx(-8'sd128),.zy(stage==6?-8'sd8:-8'sd128),.gap_m(gap_m),.gap_shift(gap_shift),.start_ready(),.busy(pb),.done(pdone),.output_valid(pvalid),.error_valid(perr),.error_code(pe),.active_job(active_job),
 .rd_valid(rdv),.rd_ready(rdr),.rd_addr(raddr),.rd_bytes(rbytes),.rd_job(rjob),.rd_rsp_valid(arsp&&po),.rd_rsp_ready(rrdy),.rd_data(adata),.rd_rsp_job(ajob),.rd_error(aerr),
 .wr_valid(wv),.wr_ready(po&&!pipeline_rst),.wr_addr(waddr),.wr_data(wdata),.obs_valid(ov),.obs_ready(po&&!pipeline_rst),.obs_job(ojob),.obs_index(oi),.obs_kind(okind),.obs_acc(oacc),.winner_valid(pwinner),.winner_index(winner),.winner_value(winner_value));
 reg [2:0] hs;reg [31:0] ha;reg [15:0] hn,index;reg [2047:0] hd;reg hw;reg [3:0] hr;
 wire host_read=hs==2;wire host_consume=hs==3;
 wire m_re;wire [19:0] m_ra;wire [31:0] m_q;wire adapter_ready;
 assign rdr=adapter_ready&&po;
 stage5_adapter adapter(clk,pipeline_rst,!co,po?rdv:host_read,adapter_ready,po?raddr:ha[19:0]+index,
 po?rbytes:3'd1,po?rjob:job,arsp,po?rrdy:host_consume,adata,ajob,aerr,m_re,m_ra,m_q,adapter_empty);
 wire host_write=hs==1;wire [19:0] write_address=po?waddr:ha[19:0]+index;
 wire [7:0] byte_data=hd[index*8+:8];
 wire [31:0] write_data=po?{24'd0,wdata}:(hr>=2?{byte_data,partial[hr-2]}:{24'd0,byte_data});
 wire mem_write=!pipeline_rst&&((po&&wv)||(host_write&&(hr<2||write_address[1:0]==3)));
 stage5_memory memory(clk,pipeline_rst,co,car,cwr,cbr,cpr,cwv,caa,cwa,cba,cbi,cpi,wb,pbase,cdata,cacc,cindex,aq,wq,bq,mq,sq,
 m_re,mem_write,m_ra,hr>=2&&!po?{write_address[19:2],2'b00}:write_address,write_data,m_q,
 po&&ov,stage==6?9'd128+oi[8:0]:oi[8:0],oacc,gap_m,gap_shift);
 function integer region(input [31:0] a);
 begin if(a>=32'h10000&&a<32'h18000)region=0;else if(a>=32'h30000&&a<32'h38c40)region=1;
 else if(a>=32'h40000&&a<32'h40394)region=2;else if(a>=32'h41000&&a<32'h41394)region=3;
 else if(a>=32'h42000&&a<32'h42394)region=4;else if(a>=32'h43000&&a<32'h43008)region=5;
 else if(a>=32'h20000&&a<32'h28000)region=6;else if(a>=32'h50000&&a<32'h50800)region=7;else region=-1;end endfunction
 function [31:0] base(input integer r);case(r)0:base='h10000;1:base='h30000;2:base='h40000;3:base='h41000;4:base='h42000;5:base='h43000;6:base='h20000;default:base='h50000;endcase endfunction
 function integer size(input integer r);case(r)0:size=2048;1:size=35904;2,3,4:size=916;5:size=8;default:size=0;endcase endfunction
 reg [7:0] check_error;integer regbase,regsize,r;reg [31:0] off;reg [32:0] last;
 // Each candidate word is independent. Do not carry an assembled-word mux
 // through the 256-byte validation loop: only the OR of invalid flags matters.
 wire [255:0] invalid_byte;
 wire [23:0] frame_partial=(r>=2)?partial[r-2]:24'd0;
 genvar check_lane;
 generate for(check_lane=0;check_lane<256;check_lane=check_lane+1)begin:frame_check
  wire [31:0] word_value;
  if(check_lane==0)assign word_value={frame_data[7:0],frame_partial};
  else if(check_lane==1)assign word_value={frame_data[15:0],frame_partial[15:0]};
  else if(check_lane==2)assign word_value={frame_data[23:0],frame_partial[7:0]};
  else assign word_value=frame_data[(check_lane-3)*8+:32];
  assign invalid_byte[check_lane]=(check_lane<frame_len)&&
   ((r==1&&frame_data[check_lane*8+:8]==8'h80)||
    (r>=2&&(((off[1:0]+check_lane)&3)==3)&&
     (((r==3||(r==5&&check_lane<4&&off==3-check_lane))&&$signed(word_value)<=0)||
      ((r==4||(r==5&&check_lane<8&&off==7-check_lane))&&word_value>62))));
 end endgenerate
 always @*begin
 check_error=0;r=region(frame_addr);off=frame_addr-base(r);last={1'b0,frame_addr}+frame_len-1;regbase=-1;regsize=0;
 case(frame_addr)
 0:begin regbase=0;regsize=4;end
 8:begin regbase=8;regsize=4;end
 16:begin regbase=16;regsize=4;end
 20:begin regbase=20;regsize=4;end
 24:begin regbase=24;regsize=4;end
 28:begin regbase=28;regsize=4;end
 32:begin regbase=32;regsize=4;end
 40,48,56,64,72:begin regbase=frame_addr;regsize=8;end
 80:begin regbase=80;regsize=4;end
 256,260:begin regbase=frame_addr;regsize=4;end
 264:begin regbase=264;regsize=16;end
 288:begin regbase=288;regsize=32;end
 320:begin regbase=320;regsize=8;end
 384:begin regbase=384;regsize=64;end
 default:;
 endcase
 if(frame_len==0||frame_len>256||last>33'hfffff)check_error=4;
 else if(r>=0)begin
 if(region(last[31:0])!=r)check_error=3;
 else if(frame_write)begin
 if(state!=1)check_error=1;
 else if(r>5)check_error=3;
 else if(off!=loaded_count[r]||off+frame_len>size(r))check_error=4;
 else begin
 if(|invalid_byte)check_error=2;
 end
 end else if(state==5)begin
 // Region geometry has already passed. Check debug authorization before cursor order.
 if(r==7)begin
 if(required_acc==0||off<(stage==6?512:0)||off+frame_len>(stage==6?512:0)+required_acc)check_error=3;
 else if(off!=(stage==6?512:0)+diag_acc)check_error=4;
 end
 // Ordinary output authorization/range precedes sequential cursor classification.
 else if(r!=((stage==1||stage==3||stage==5)?0:6)||off+frame_len>required_output||stage==7)check_error=3;
 else if(off!=diag_output)check_error=4;
 end else if(!(state==6&&output_valid&&r==6&&off+frame_len<=5))check_error=6;
 end else if(regbase<0||frame_len!=regsize)check_error=3;
 else if(frame_write)begin
 case(frame_addr)
 256:begin
 case(frame_data[31:0])
 32'h53000001:if(!(state==0||state==6||state==7))check_error=1;
 32'h53000002:if(state!=1)check_error=1;else if(!all_loaded||session==0)check_error=6;
 32'h53000003:if(state!=5)check_error=6;else if(!context_valid||resume_context!={token,job,session})check_error=10;else if(diag_output!=required_output||diag_acc!=required_acc)check_error=6;
 32'h53000004:if(state==2||state==3||state==4||state==5)check_error=1;
 32'h53000005:;
 default:check_error=8;endcase end
 260:if(!(state==0||state==1))check_error=1;else if(frame_data[31:1]!=0)check_error=2;
 264:if(state!=5)check_error=6;
 320:if(state!=1)check_error=1;else if(frame_data[63:0]==0)check_error=2;
 default:check_error=3;
 endcase
 end else if(frame_addr==256||frame_addr==264)check_error=3;
 end
 reg [511:0] error_record;reg [7:0] sticky_error,previous_ctl_error;reg [3:0] prev_state;
 // ABORT/timeout win in the controller even if a producer error is still high.
 // Only attribute a producer when its mapped code is the selected fatal code.
 wire record_post=perr&&ctl_error==(pe==5?8'd7:8'd2);
 wire record_conv=ce!=0&&ctl_error==ce&&ctl_error!=9&&ctl_error!=11;
 reg [1:0] pending_diag;reg [15:0] pending_diag_len;
 // rst already asserts asynchronously through reset_sync and releases on clk.
 // Raw reset_n must not also drive ordinary transaction data/enable paths.
 assign frame_ready=hs==0&&!reply_valid&&!rst;
 task record_error(input [7:0] code,input [31:0] source,input [7:0] local_code,input [31:0] failed_address,input [31:0] operation);begin
 sticky_error<=code;error_record<={os,vs,operation,failed_address,token,job,session,29'd0,stage,24'd0,code,24'd0,local_code,source,32'd1,32'd1};
 end endtask
 integer j;
 always @(posedge clk)begin
 if(rst)begin
 hs<=0;ha<=0;hn<=0;index<=0;hd<=0;hw<=0;hr<=0;reply_valid<=0;reply_error<=0;reply_len<=0;reply_data<=0;
 begin_load<=0;start<=0;resume<=0;abort_job<=0;clear_error<=0;diag<=0;session<=0;resume_context<=0;context_valid<=0;
 diag_output<=0;diag_acc<=0;error_record<=0;sticky_error<=0;previous_ctl_error<=0;prev_state<=0;pending_diag<=0;pending_diag_len<=0;
 for(j=0;j<6;j=j+1)loaded_count[j]<=0;for(j=0;j<4;j=j+1)partial[j]<=0;
 end else begin
 begin_load<=0;start<=0;resume<=0;abort_job<=0;clear_error<=0;prev_state<=state;previous_ctl_error<=ctl_error;
 if(ctl_error!=0&&ctl_error!=previous_ctl_error)
 record_error(ctl_error,record_post?32'd2:record_conv?32'd3:32'd1,record_post?pe:record_conv?ce:ctl_error,
 record_post&&pe==4?{12'd0,raddr}:32'hffffffff,record_post&&pe==4?32'd0:32'hffffffff);
 if(state==7&&prev_state!=7)begin session<=0;context_valid<=0;for(j=0;j<6;j=j+1)loaded_count[j]<=0;end
 // Initialize at the transition edge, before the first PAUSED request.
 if(state==4&&adapter_empty&&!cb&&!pb)begin diag_output<=0;diag_acc<=0;context_valid<=0;end
 if(reply_valid&&reply_ready)reply_valid<=0;
 if(reply_sent)begin if(pending_diag==1)diag_output<=diag_output+pending_diag_len;if(pending_diag==2)diag_acc<=diag_acc+pending_diag_len;pending_diag<=0;end
 if(frame_valid&&frame_ready)begin
 ha<=frame_addr;hn<=frame_len;hd<=frame_data;hw<=frame_write;index<=0;hr<=r;reply_data<=0;reply_error<=check_error;reply_len<=0;pending_diag<=0;
 if(check_error!=0)begin reply_valid<=1;record_error(check_error,32'd0,check_error,frame_addr,{31'd0,frame_write});end
 else if(r>=0)begin hs<=frame_write?1:2;end
 else begin
 reply_valid<=1;reply_len<=frame_write?0:frame_len;
 if(frame_write)case(frame_addr)
 256:case(frame_data[31:0])
 32'h53000001:begin begin_load<=1;session<=0;context_valid<=0;for(j=0;j<6;j=j+1)loaded_count[j]<=0;for(j=0;j<4;j=j+1)partial[j]<=0;end
 32'h53000002:begin start<=1;context_valid<=0;end
 32'h53000003:begin resume<=1;end
 32'h53000004:begin clear_error<=1;sticky_error<=0;error_record[63:32]<=0;end
 32'h53000005:abort_job<=1;
 endcase
 260:diag<=frame_data[0];264:begin resume_context<=frame_data[127:0];context_valid<=1;end
 320:session<=frame_data[63:0];endcase
 else case(frame_addr)
 0:reply_data<=32'h50003;16:reply_data<={26'd0,state==7,state==5,output_valid,state==1,state==6,(state>=2&&state<=5)};
 20:reply_data<={24'd0,sticky_error};8:reply_data<=32'h1f;24:reply_data<=job;28:reply_data<=state==0||state==1?32'hffffffff:{29'd0,stage};32:reply_data<=token;
 40:reply_data<=ns;48:reply_data<=vs;56:reply_data<=os;64:reply_data<=cycles;72:reply_data<=pauses;
 80:begin reply_data<=pwinner&&((state==5&&stage==7)||state==6)?{1'b1,15'd0,winner_value,5'd0,winner}:32'd0;if(state==5&&stage==7&&diag_output==0)begin pending_diag<=1;pending_diag_len<=4;end end
 260:reply_data<=diag;288:reply_data<={32'd0,loaded_count[5],loaded_count[4],loaded_count[3],loaded_count[2],loaded_count[1],32'd0,loaded_count[0]};320:reply_data<=session;384:reply_data<=error_record;
 endcase
 end end
 if(hs==1)begin
 loaded_count[hr]<=loaded_count[hr]+1;
 if(hr>=2&&write_address[1:0]!=3)partial[hr-2][write_address[1:0]*8+:8]<=byte_data;
 if(index+1==hn)begin hs<=0;reply_valid<=1;reply_error<=0;reply_len<=0;end else index<=index+1;
 end
 if(hs==2&&adapter_ready)hs<=3;
 if(hs==3&&arsp)begin
 reply_data[index*8+:8]<=adata[7:0];
 if(index+1==hn)begin hs<=0;reply_valid<=1;reply_error<=0;reply_len<=hn;if(state==5)begin pending_diag<=hr==7?2:1;pending_diag_len<=hn;end end
 else begin index<=index+1;hs<=2;end
 end
 if(state!=5)context_valid<=0;
 end end
endmodule

module stage5_wire_top(input wire clk,reset_n,rx_valid,input wire [7:0] rx_data,input wire rx_error,
 output wire tx_valid,input wire tx_ready,output wire [7:0] tx_data);
 (* ASYNC_REG="TRUE" *) reg [1:0] sync;
 always @(posedge clk or negedge reset_n)if(!reset_n)sync<=0;else sync<={sync[0],1'b1};
 wire fv,fr,fw,rv,rr,sent;wire [31:0] a;wire [15:0] n,rn;wire [2047:0] d,rd;wire [7:0] e;
 stage5_bridge bridge(clk,!sync[1],rx_valid,rx_data,rx_error,tx_valid,tx_ready,tx_data,fv,fr,fw,a,n,d,rv,rr,e,rn,rd,sent);
 stage5_top system(clk,reset_n,fv,fr,fw,a,n,d,rv,rr,sent,e,rn,rd);
endmodule

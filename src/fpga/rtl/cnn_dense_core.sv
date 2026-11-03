// hardware-contract-v1 byte endpoint. PE_COUNT=1 only; no UART framing.
module cnn_dense_core #(parameter PE_COUNT=1)(
 input wire clk,reset_n, input wire req_valid, output wire req_ready,
 input wire req_write, input wire [19:0] req_addr, input wire [7:0] req_wdata,
 output wire rsp_valid, input wire rsp_ready, output reg [7:0] rsp_rdata,rsp_error);
 (* ASYNC_REG="TRUE" *) reg [1:0] reset_sync;
 always @(posedge clk or negedge reset_n)
  if(!reset_n)reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
 wire rst=!reset_sync[1];
 // Cancel external transactions immediately on asynchronous reset assertion.
 // RAM-driving state resets synchronously, avoiding untimed async changes at
 // BRAM address/enable pins (Vivado REQP-1840). Release remains two-stage synced.
 reg rsp_valid_i;
 assign rsp_valid=!rst&&rsp_valid_i;
 reg busy,done,load_active,output_valid,counter_overflow;
 reg [7:0] error_code,job_id;
 reg [7:0] shadow[0:12],cfg[0:12];
 wire [15:0] cin={cfg[1],cfg[0]},cout={cfg[3],cfg[2]},len={cfg[5],cfg[4]};
 wire [7:0] kernel=cfg[6],pad=cfg[8];
 wire signed [7:0] zx=cfg[10],zy=cfg[11];
 wire [15:0] lout=len+{8'd0,pad}*2-{8'd0,kernel}+1;
 reg [15:0] input_size,output_size,weight_size,param_size;
 wire [15:0] scin={shadow[1],shadow[0]},scout={shadow[3],shadow[2]},slen={shadow[5],shadow[4]};
 wire signed [31:0] slo={16'd0,slen}+{24'd0,shadow[8]}*2-{24'd0,shadow[6]}+1;
 wire [31:0] sa=scin*slen,sb=scout*slo,sw=scout*scin*shadow[6];
 wire legal=(PE_COUNT==1)&&scin>=1&&scin<=64&&scout>=1&&scout<=128&&slen>=1&&slen<=1024&&
  shadow[6]>=1&&shadow[6]<=7&&shadow[7]==1&&shadow[8]<=3&&shadow[12]<=1&&
  slo>=1&&slo<=1024&&sa<=32768&&sb<=32768&&sw<=24576;
 reg [15:0] loaded[0:4]; reg [23:0] partial[0:2];
 reg [63:0] cycles,scanned,issued_macs,committed,snapshot[0:3];
 reg [9:0] debug_count;
 reg [1:0] bus_state; reg bw;reg [19:0] ba;reg [7:0] bd;
 reg [7:0] pending_data,pending_error;reg [3:0] pending_mem;
 assign req_ready=!rst && bus_state==0 && !rsp_valid;
 wire execute=bus_state==1;
 integer region,offset,j;
 reg [7:0] berr,brdata;reg [3:0] read_mem;
 reg host_we,host_re; reg [31:0] assembled;
 reg [63:0] cvalue;
 // Decode before issuing any RAM enable. Region-local high watermarks are independent.
 always @* begin
  region=-1;offset=0;
  if(ba>=20'h10000&&ba<20'h18000)begin region=0;offset=ba-20'h10000;end
  if(ba>=20'h30000&&ba<20'h36000)begin region=1;offset=ba-20'h30000;end
  if(ba>=20'h40000&&ba<20'h40200)begin region=2;offset=ba-20'h40000;end
  if(ba>=20'h41000&&ba<20'h41200)begin region=3;offset=ba-20'h41000;end
  if(ba>=20'h42000&&ba<20'h42200)begin region=4;offset=ba-20'h42000;end
  if(ba>=20'h20000&&ba<20'h28000)begin region=5;offset=ba-20'h20000;end
  if(ba>=20'h50000&&ba<20'h50800)begin region=6;offset=ba-20'h50000;end
  berr=0;brdata=0;read_mem=0;host_we=0;host_re=0;assembled=0;cvalue=0;
  if(region>=2&&region<=4)assembled={bd,partial[region-2]};
  if(busy && (bw || region>=0))berr=1;
  else if(region>=0)begin
   if((region==0&&offset>=input_size)||(region==1&&offset>=weight_size)||
      (region>=2&&region<=4&&offset>=param_size)||(region==5&&offset>=output_size)||
      (region==6&&offset>=debug_count*4))berr=3;
   else if(bw)begin
    if(region>=5)berr=3;
    else if(!load_active)berr=6;
    else if(offset!=loaded[region])berr=4;
    else if(region==1&&bd==8'h80)berr=2;
    else if(region==3&&offset%4==3&&($signed(assembled)<=0))berr=2;
    else if(region==4&&offset%4==3&&assembled>62)berr=2;
    else host_we=execute;
   end else begin
    if(region>=5&&!output_valid)berr=6;
    else if(region<2&&offset>=loaded[region])berr=6;
    else if(region>=2&&region<=4&&offset>=(loaded[region]&16'hfffc))berr=6;
    else begin host_re=execute;read_mem=region+1;end
   end
  end else if(ba>=16&&ba<=28)begin
   brdata=shadow[ba-16];
   if(bw&&load_active)berr=1;
  end else if(ba==4)begin
   if(bw)case(bd)
    8:if(!legal)berr=2;
    1:if(cfg[9]!=0)berr=8;
      else if(!load_active||loaded[0]!=input_size||loaded[1]!=weight_size||
       loaded[2]!=param_size||loaded[3]!=param_size||loaded[4]!=param_size)berr=6;
    2,4:;
    default:berr=2;
   endcase
  end else if(bw)berr=3;
  else if(ba<4)brdata=(ba==0)?1:0;
  else if(ba>=8&&ba<12)brdata=(ba==8)?{3'd0,counter_overflow,output_valid,load_active,done,busy}:0;
  else if(ba==12)brdata=error_code;
  else if(ba==32||ba==33)brdata=(debug_count>>((ba-32)*8));
  else if(ba>=40&&ba<72)begin
   case((ba-40)/8)0:cvalue=cycles;1:cvalue=scanned;2:cvalue=issued_macs;3:cvalue=committed;endcase
   if(ba[2:0]!=0)cvalue=snapshot[(ba-40)/8];
   brdata=cvalue>>(ba[2:0]*8);
  end else if(ba>=72&&ba<76)brdata=32'h601>>((ba-72)*8);
  else if(ba==76)brdata=job_id;
  else berr=3;
 end
 wire start_job=execute&&bw&&ba==4&&bd==1&&berr==0;
 wire begin_load=execute&&bw&&ba==4&&bd==8&&berr==0;
 wire pipe_reset=rst||!busy;
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
 wire [7:0] aq,wq,bq;wire [31:0] biasq,mq,shiftq,debugq;
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
 wire b_ready=1'b1;
 wire b_valid=busy&&rs==2&&rq_ov&&!rq_error;
 wire b_commit=b_valid&&b_ready;
 wire [14:0] b_addr=result_tag[38:32]*lout+result_tag[48:39];
 requant_even requant(clk,pipe_reset,busy&&rs==1,rq_ir,$signed(result_tag[31:0]),
  $signed(mq),shiftq,zy,cfg[12][0],rq_ov,b_ready&&rs==2,rq_data,rq_error);
 dense_ram #(.WIDTH(8),.DEPTH(32768),.AW(15)) ram_a(clk,
  host_we&&region==0,ba[14:0],bd,
  (host_re&&region==0)||(mem_issue&&!padding),busy?a_addr:ba[14:0],aq);
 dense_ram #(.WIDTH(8),.DEPTH(24576),.AW(15)) ram_w(clk,
  host_we&&region==1,ba[14:0],bd,
  (host_re&&region==1)||weight_read,busy?w_addr:ba[14:0],wq);
 dense_ram #(.WIDTH(8),.DEPTH(32768),.AW(15)) ram_b(clk,
  b_commit,b_addr,rq_data,host_re&&region==5,ba[14:0],bq);
 dense_ram #(.WIDTH(32),.DEPTH(128),.AW(7)) ram_bias(clk,
  host_we&&region==2&&ba[1:0]==3,ba[8:2],assembled,
  (host_re&&region==2)||(busy&&ss==S_BIAS),busy?oc:ba[8:2],biasq);
 dense_ram #(.WIDTH(32),.DEPTH(128),.AW(7)) ram_m(clk,
  host_we&&region==3&&ba[1:0]==3,ba[8:2],assembled,
  (host_re&&region==3)||param_read,busy?rf_od[38:32]:ba[8:2],mq);
 dense_ram #(.WIDTH(32),.DEPTH(128),.AW(7)) ram_shift(clk,
  host_we&&region==4&&ba[1:0]==3,ba[8:2],assembled,
  (host_re&&region==4)||param_read,busy?rf_od[38:32]:ba[8:2],shiftq);
 dense_ram #(.WIDTH(32),.DEPTH(512),.AW(9)) ram_debug(clk,
  b_commit&&debug_count<512,debug_count[8:0],result_tag[31:0],
  host_re&&region==6,ba[10:2],debugq);
 // Counter saturation is explicit rather than inferred from expected work.
 function [63:0] inc64(input [63:0] v);inc64=(&v)?v:v+1;endfunction
 always @(posedge clk) begin
  if(rst) begin
   busy<=0;done<=0;load_active<=0;output_valid<=0;counter_overflow<=0;error_code<=0;job_id<=0;
   cycles<=0;scanned<=0;issued_macs<=0;committed<=0;debug_count<=0;
   bus_state<=0;rsp_valid_i<=0;rsp_rdata<=0;rsp_error<=0;bw<=0;ba<=0;bd<=0;
   pending_data<=0;pending_error<=0;pending_mem<=0;
   input_size<=0;output_size<=0;weight_size<=0;param_size<=0;
   for(j=0;j<13;j=j+1)begin shadow[j]<=0;cfg[j]<=0;end
   shadow[7]<=1;shadow[12]<=1;
   for(j=0;j<5;j=j+1)loaded[j]<=0;
   for(j=0;j<3;j=j+1)partial[j]<=0;
   for(j=0;j<4;j=j+1)snapshot[j]<=0;
   ss<=S_IDLE;rs<=0;oc<=0;pos<=0;ci<=0;ki<=0;scan_finished<=0;candidate<=0;result_tag<=0;
  end else begin
   if(rsp_valid&&rsp_ready)rsp_valid_i<=0;
   if(req_valid&&req_ready)begin ba<=req_addr;bd<=req_wdata;bw<=req_write;bus_state<=1;end
   if(execute)begin
    pending_data<=brdata;pending_error<=berr;pending_mem<=read_mem;bus_state<=2;
    if(berr!=0)error_code<=berr;
    else begin
     if(bw&&ba>=16&&ba<=28)shadow[ba-16]<=bd;
     if(host_we)begin
      loaded[region]<=loaded[region]+1;
      if(region>=2&&ba[1:0]!=3)partial[region-2][ba[1:0]*8+:8]<=bd;
     end
     if(!bw&&ba>=40&&ba<72&&ba[2:0]==0)snapshot[(ba-40)/8]<=cvalue;
     if(bw&&ba==4)begin
      if(bd==2)done<=0;
      if(bd==4)error_code<=0;
     end
    end
   end
   if(bus_state==2)begin
    bus_state<=0;rsp_valid_i<=1;rsp_error<=pending_error;
    case(pending_mem)
     1:rsp_rdata<=aq;2:rsp_rdata<=wq;3:rsp_rdata<=biasq>>(ba[1:0]*8);
     4:rsp_rdata<=mq>>(ba[1:0]*8);5:rsp_rdata<=shiftq>>(ba[1:0]*8);
     6:rsp_rdata<=bq;7:rsp_rdata<=debugq>>(ba[1:0]*8);default:rsp_rdata<=pending_data;
    endcase
   end
   if(begin_load)begin
    for(j=0;j<13;j=j+1)cfg[j]<=shadow[j];
    for(j=0;j<5;j=j+1)loaded[j]<=0;
    for(j=0;j<3;j=j+1)partial[j]<=0;
    input_size<=sa[15:0];output_size<=sb[15:0];weight_size<=sw[15:0];param_size<=scout*4;
    load_active<=1;output_valid<=0;done<=0;debug_count<=0;job_id<=job_id+1;
   end
   if(start_job)begin
    busy<=1;load_active<=0;done<=0;output_valid<=0;cycles<=0;scanned<=0;issued_macs<=0;committed<=0;counter_overflow<=0;
    ss<=S_BIAS;rs<=0;oc<=0;pos<=0;ci<=0;ki<=0;scan_finished<=0;
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
     busy<=0;done<=0;output_valid<=0;load_active<=0;ss<=S_IDLE;rs<=0;error_code<=7;
    end
   end
  end
 end
endmodule

// Frozen v1 frame parser. One frame and one core byte in flight.
// Payload buffer is reused only after complete request verification/execution.
module stage3_bridge(input wire clk,rst,input wire rx_valid,input wire [7:0] rx_data,
 input wire rx_error,output wire tx_valid,input wire tx_ready,output reg [7:0] tx_data,
 output wire req_valid,input wire req_ready,output wire req_write,
 output wire [19:0] req_addr,output wire [7:0] req_wdata,
 input wire rsp_valid,output wire rsp_ready,input wire [7:0] rsp_rdata,rsp_error);
 localparam RX=0,STATUS_REQ=1,STATUS_RSP=2,CHECK=3,EXEC_REQ=4,EXEC_RSP=5,REPLY=6;
 reg [2:0] state=RX;
 (* ram_style="distributed" *) reg [7:0] payload[0:255];
 reg [8:0] pos=0,index=0,txpos=0;reg [7:0] opcode=0,status=0,live_status=0;
 reg [15:0] seq=0,length=0,crc=16'hffff,wire_crc=0,reply_len=0,txcrc=16'hffff;
 reg [31:0] address=0;reg [22:0] timeout_count=0;
 reg [7:0] shadow[0:12];reg [15:0] sizes[0:4],loaded[0:4];
 wire [15:0] ci={shadow[1],shadow[0]},co={shadow[3],shadow[2]},ln={shadow[5],shadow[4]};
 wire [31:0] outlen=ln+2*shadow[8]-shadow[6]+1;
 reg [15:0] output_size=0;
 function [15:0] crcbyte(input [15:0] old,input [7:0] b);
  reg [15:0] c;integer k;begin c=old^{b,8'd0};for(k=0;k<8;k=k+1)c=c[15]?(c<<1)^16'h1021:c<<1;crcbyte=c;end
 endfunction
 wire [32:0] endaddr={1'b0,address}+length-1;
 wire [31:0] checkaddr=address+index;
 integer region,startregion,off,j;reg [7:0] checkerror;
 function integer decode(input [31:0] a);
 begin
  if(a>=32'h10000&&a<32'h18000)decode=0;
  else if(a>=32'h30000&&a<32'h36000)decode=1;
  else if(a>=32'h40000&&a<32'h40200)decode=2;
  else if(a>=32'h41000&&a<32'h41200)decode=3;
  else if(a>=32'h42000&&a<32'h42200)decode=4;
  else if(a>=32'h20000&&a<32'h28000)decode=5;
  else if(a>=32'h50000&&a<32'h50800)decode=6;
  else decode=-1;
 end endfunction
 function [31:0] base(input integer r);
 case(r)0:base='h10000;1:base='h30000;2:base='h40000;3:base='h41000;4:base='h42000;5:base='h20000;default:base='h50000;endcase
 endfunction
 always @*begin
  region=decode(checkaddr);startregion=decode(address);off=checkaddr-base(region);checkerror=0;
  if(address[31:20]!=0||endaddr>33'hfffff)checkerror=3;
  // Legal single-byte CMD must reach the core: it owns START/BUSY decisions
  // and the sticky ERROR register. Invalid/range/permission frames still never
  // issue a write. Core rejects BUSY commands without modifying the running job.
  else if(live_status[0]&&(opcode==0||region>=0)&&
   !(opcode==0&&address==4&&length==1&&
     (payload[0]==1||payload[0]==2||payload[0]==4||payload[0]==8)))checkerror=1;
  else if(region!=startregion)checkerror=3;
  else if(region>=0)begin
   if((region<5&&off>=sizes[region])||(region==5&&off>=output_size)||
      (region==6&&off>=((output_size<512)?output_size:512)*4))checkerror=3;
   else if(opcode==0)begin
    if(region>=5)checkerror=3;
    else if(!live_status[2])checkerror=6;
    else if(address-base(region)!=loaded[region])checkerror=4;
   end else begin
    if(region>=5&&!live_status[3])checkerror=6;
    else if(region<2&&off>=loaded[region])checkerror=6;
    else if(region>=2&&region<5&&off>=(loaded[region]&16'hfffc))checkerror=6;
   end
  end else if(checkaddr>=16&&checkaddr<=28)begin
   if(opcode==0&&live_status[2])checkerror=1;
  end else if(checkaddr==4)begin
   if(length!=1)checkerror=4;
   else if(opcode==0&&payload[0]!=1&&payload[0]!=2&&payload[0]!=4&&payload[0]!=8)checkerror=2;
  end else if(opcode==0)checkerror=3;
  else if(!(checkaddr<4||(checkaddr>=8&&checkaddr<12)||checkaddr==12||
    checkaddr==32||checkaddr==33||(checkaddr>=40&&checkaddr<=76)))checkerror=3;
 end
 assign req_valid=!rst&&(state==STATUS_REQ||state==EXEC_REQ);
 assign req_write=state==EXEC_REQ&&opcode==0;
 assign req_addr=state==STATUS_REQ?20'd8:address[19:0]+index;
 assign req_wdata=payload[index[7:0]];
 assign rsp_ready=!rst&&(state==STATUS_RSP||state==EXEC_RSP);
 assign tx_valid=!rst&&state==REPLY;
 always @*begin
  case(txpos)
   0:tx_data=8'h5a;1:tx_data=8'ha5;2:tx_data=status;3:tx_data=seq[7:0];4:tx_data=seq[15:8];
   5:tx_data=reply_len[7:0];6:tx_data=reply_len[15:8];
   default:if(txpos<7+reply_len)tx_data=payload[txpos-7];else if(txpos==7+reply_len)tx_data=txcrc[7:0];else tx_data=txcrc[15:8];
  endcase
 end
 task reply(input [7:0] code,input [15:0] n);
 begin status<=code;reply_len<=n;txpos<=0;txcrc<=16'hffff;state<=REPLY;pos<=0;timeout_count<=0;end
 endtask
 always @(posedge clk)begin
  if(rst)begin
   state<=RX;pos<=0;index<=0;txpos<=0;timeout_count<=0;crc<=16'hffff;seq<=0;length<=0;address<=0;opcode<=0;
   wire_crc<=0;reply_len<=0;status<=0;txcrc<=16'hffff;live_status<=0;output_size<=0;
   for(j=0;j<13;j=j+1)shadow[j]<=0;shadow[7]<=1;shadow[12]<=1;
   for(j=0;j<5;j=j+1)begin sizes[j]<=0;loaded[j]<=0;end
  end else case(state)
   RX:begin
    if(pos!=0&&!rx_valid)begin
     if(timeout_count==4999999)begin
      if(pos>=11)reply(5,0);else begin pos<=0;timeout_count<=0;end
     end else timeout_count<=timeout_count+1;
    end
    if(rx_error)begin if(pos>=11)reply(5,0);else begin pos<=0;timeout_count<=0;end end
    else if(rx_valid)begin
     timeout_count<=0;
     if(pos==0)begin if(rx_data==8'ha5)pos<=1;end
     else if(pos==1)begin if(rx_data==8'h5a)begin pos<=2;crc<=16'hffff;end else if(rx_data!=8'ha5)pos<=0;end
     else begin
      pos<=pos+1;
      if(pos<11||(opcode==0&&pos<11+length))crc<=crcbyte(crc,rx_data);
      case(pos)
       2:opcode<=rx_data;3:seq[7:0]<=rx_data;4:seq[15:8]<=rx_data;
       5:address[7:0]<=rx_data;6:address[15:8]<=rx_data;7:address[23:16]<=rx_data;8:address[31:24]<=rx_data;
       9:length[7:0]<=rx_data;
       10:begin length[15:8]<=rx_data;if(opcode>1||{rx_data,length[7:0]}==0||{rx_data,length[7:0]}>256)reply(5,0);end
       default:begin
        if(opcode==0&&pos<11+length)payload[pos-11]<=rx_data;
        else if(pos==11+((opcode==0)?length:0))wire_crc[7:0]<=rx_data;
        else if({rx_data,wire_crc[7:0]}!=crc)reply(5,0);
        else begin state<=STATUS_REQ;index<=0;end
       end
      endcase
     end
    end
   end
   STATUS_REQ:if(req_ready)state<=STATUS_RSP;
   STATUS_RSP:if(rsp_valid)begin if(rsp_error!=0)reply(rsp_error,0);else begin live_status<=rsp_rdata;state<=CHECK;index<=0;end end
   CHECK:if(checkerror!=0)reply(checkerror,0);else if(index+1==length)begin index<=0;state<=EXEC_REQ;end else index<=index+1;
   EXEC_REQ:if(req_ready)state<=EXEC_RSP;
   EXEC_RSP:if(rsp_valid)begin
    if(rsp_error!=0)reply(rsp_error,0);
    else begin
     if(opcode==1)payload[index[7:0]]<=rsp_rdata;
     else begin
      if(address+index>=16&&address+index<=28)shadow[address+index-16]<=payload[index[7:0]];
      if(startregion>=0&&startregion<5)loaded[startregion]<=loaded[startregion]+1;
      if(address==4&&payload[0]==8)begin
       sizes[0]<=ci*ln;sizes[1]<=co*ci*shadow[6];sizes[2]<=co*4;sizes[3]<=co*4;sizes[4]<=co*4;output_size<=co*outlen;
       for(j=0;j<5;j=j+1)loaded[j]<=0;
      end
     end
     if(index+1==length)reply(0,opcode==1?length:0);else begin index<=index+1;state<=EXEC_REQ;end
    end
   end
   REPLY:if(tx_ready)begin
    if(txpos>=2&&txpos<7+reply_len)txcrc<=crcbyte(txcrc,tx_data);
    if(txpos==8+reply_len)begin state<=RX;pos<=0;end else txpos<=txpos+1;
   end
  endcase
 end
endmodule

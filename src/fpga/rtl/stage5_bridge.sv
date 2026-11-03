// Fork of stage3_bridge frame format/CRC. Validated complete frames to executor.
module stage5_bridge(input wire clk,rst,rx_valid,input wire [7:0] rx_data,input wire rx_error,
 output wire tx_valid,input wire tx_ready,output reg [7:0] tx_data,
 output wire frame_valid,input wire frame_ready,output reg write,
 output reg [31:0] address,output reg [15:0] length,output reg [2047:0] payload,
 input wire reply_valid,output wire reply_ready,input wire [7:0] reply_error,
 input wire [15:0] reply_length,input wire [2047:0] reply_payload,output reg reply_sent);
 localparam RX=0,EXEC=1,WAIT=2,TX=3;
 reg [1:0] state;reg [9:0] pos,tp;reg [15:0] seq,crc,lowcrc,tcrc,n;
 reg [7:0] op,status;reg [22:0] idle_count;
 reg [2047:0] result;
 // Decode each byte's write enable directly. A 32-bit arithmetic part-select
 // synthesized into a very large update mux for the entire 2048-bit payload.
 // Legal payload positions are 11..266, including all 256 bytes.
 genvar byte_lane;
 generate for(byte_lane=0;byte_lane<256;byte_lane=byte_lane+1)begin:payload_lane
  always @(posedge clk)begin
   if(rst)payload[byte_lane*8+:8]<=0;
   else if(state==RX&&!rx_error&&rx_valid&&op==0&&pos==11+byte_lane&&pos<11+length)
    payload[byte_lane*8+:8]<=rx_data;
  end
 end endgenerate
 // Ten-bit subtraction preserves the bridge's 10-bit position range, while
 // avoiding a 32-bit unsized expression driving the byte selection network.
 wire [9:0] result_byte_index=tp-10'd7;
 function [15:0] crcbyte(input [15:0] old,input [7:0] b);
 reg [15:0] c;integer k;begin c=old^{b,8'd0};for(k=0;k<8;k=k+1)c=c[15]?(c<<1)^16'h1021:c<<1;crcbyte=c;end endfunction
 assign frame_valid=state==EXEC&&!rst;assign reply_ready=state==WAIT&&!rst;assign tx_valid=state==TX&&!rst;
 task respond(input [7:0] e);begin status<=e;n<=0;tp<=0;tcrc<=16'hffff;state<=TX;end endtask
 always @*case(tp)
 0:tx_data=8'h5a;1:tx_data=8'ha5;2:tx_data=status;3:tx_data=seq[7:0];4:tx_data=seq[15:8];5:tx_data=n[7:0];6:tx_data=n[15:8];
 default:if(tp<7+n)tx_data=result[{result_byte_index,3'b000}+:8];else if(tp==7+n)tx_data=tcrc[7:0];else tx_data=tcrc[15:8];endcase
 always @(posedge clk)begin
 if(rst)begin state<=RX;pos<=0;tp<=0;seq<=0;crc<=16'hffff;tcrc<=16'hffff;lowcrc<=0;n<=0;op<=0;status<=0;idle_count<=0;result<=0;address<=0;length<=0;write<=0;reply_sent<=0;end
 else begin
 reply_sent<=0;
 case(state)
 RX:begin
 if(pos!=0&&!rx_valid)begin if(idle_count==4999999)respond(5);else idle_count<=idle_count+1;end
 if(rx_error)respond(5);
 else if(rx_valid)begin
 idle_count<=0;
 if(pos==0)begin if(rx_data==8'ha5)pos<=1;end
 else if(pos==1)begin if(rx_data==8'h5a)begin pos<=2;crc<=16'hffff;end else if(rx_data!=8'ha5)pos<=0;end
 else begin
 pos<=pos+1;
 if(pos<11||(op==0&&pos<11+length))crc<=crcbyte(crc,rx_data);
 case(pos)
 2:begin op<=rx_data;write<=rx_data==0;end
 3:seq[7:0]<=rx_data;4:seq[15:8]<=rx_data;
 5:address[7:0]<=rx_data;6:address[15:8]<=rx_data;7:address[23:16]<=rx_data;8:address[31:24]<=rx_data;
 9:length[7:0]<=rx_data;
 10:begin length[15:8]<=rx_data;if(op>1||{rx_data,length[7:0]}==0||{rx_data,length[7:0]}>256)respond(5);end
 default:begin
 if(op==0&&pos<11+length)begin end // payload_lane writes the addressed byte
 else if(pos==11+((op==0)?length:0))lowcrc[7:0]<=rx_data;
 else if({rx_data,lowcrc[7:0]}!=crc)respond(5);
 else state<=EXEC;
 end endcase
 end end
 end
 EXEC:if(frame_ready)state<=WAIT;
 WAIT:if(reply_valid)begin status<=reply_error;n<=reply_length;result<=reply_payload;tp<=0;tcrc<=16'hffff;state<=TX;end
 TX:if(tx_ready)begin
 if(tp>=2&&tp<7+n)tcrc<=crcbyte(tcrc,tx_data);
 if(tp==8+n)begin reply_sent<=1;state<=RX;pos<=0;idle_count<=0;end else tp<=tp+1;
 end
 endcase
 end end
endmodule

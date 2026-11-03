// Single 50MHz clock, nominal 115200 8N1 (434 clocks/bit).
module stage3_uart_rx(input wire clk,rst,input wire rx,output reg valid,
 output reg [7:0] data,output reg framing_error);
 (* ASYNC_REG="TRUE" *) reg [1:0] rx_sync=2'b11;
 always @(posedge clk) if(rst)rx_sync<=3;else rx_sync<={rx_sync[0],rx};
 reg [1:0] state=0;reg [8:0] count=0;reg [2:0] bitno=0;reg [7:0] shift=0;
 always @(posedge clk)begin
  valid<=0;framing_error<=0;
  if(rst)begin state<=0;count<=0;data<=0;shift<=0;bitno<=0;end
  else case(state)
   0:if(!rx_sync[1])begin state<=1;count<=216;end
   1:if(count!=0)count<=count-1;else if(rx_sync[1])state<=0;else begin state<=2;count<=433;bitno<=0;end
   2:if(count!=0)count<=count-1;else begin shift[bitno]<=rx_sync[1];count<=433;if(bitno==7)state<=3;else bitno<=bitno+1;end
   3:if(count!=0)count<=count-1;else begin state<=0;if(rx_sync[1])begin data<=shift;valid<=1;end else framing_error<=1;end
  endcase
 end
endmodule
module stage3_uart_tx(input wire clk,rst,input wire valid,output wire ready,
 input wire [7:0] data,output wire tx);
 reg [9:0] shift=10'h3ff;reg [8:0] count=0;reg [3:0] remaining=0;
 assign ready=remaining==0&&!rst;assign tx=rst?1'b1:shift[0];
 always @(posedge clk)begin
  if(rst)begin shift<=10'h3ff;count<=0;remaining<=0;end
  else if(ready&&valid)begin shift<={1'b1,data,1'b0};remaining<=10;count<=433;end
  else if(remaining!=0)begin
   if(count!=0)count<=count-1;else begin shift<={1'b1,shift[9:1]};remaining<=remaining-1;count<=433;end
  end
 end
endmodule

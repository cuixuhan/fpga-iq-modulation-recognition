// Pin wrapper follows the protected cnn_bringup_top wiring; never programmed here.
module stage5_board_top(input wire sys_clk,sys_rst_n,uart_rx,output wire uart_tx);
 (* ASYNC_REG="TRUE" *) reg [1:0] reset_sync=0;
 always @(posedge sys_clk or negedge sys_rst_n)
 if(!sys_rst_n)reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
 wire rst=!reset_sync[1];wire rv,re,tv,tr;wire [7:0] rd,td;
 stage3_uart_rx receiver(sys_clk,rst,uart_rx,rv,rd,re);
 stage3_uart_tx transmitter(sys_clk,rst,tv,tr,td,uart_tx);
 stage5_wire_top system(sys_clk,sys_rst_n,rv,rd,re,tv,tr,td);
endmodule

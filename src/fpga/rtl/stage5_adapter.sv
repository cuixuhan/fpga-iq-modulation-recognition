module stage5_adapter(input wire clk,rst,enable,input wire valid,output wire ready,
 input wire [19:0] addr,input wire [2:0] bytes,input wire [31:0] job,
 output reg rsp_valid,input wire rsp_ready,output reg [31:0] data,rsp_job,output reg error,
 output wire ram_re,output reg [19:0] ram_addr,input wire [31:0] ram_q,output wire drained);
 reg [1:0] state;reg [2:0] size;
 assign ready=enable&&!rst&&state==0;
 assign ram_re=!rst&&state==1;
 assign drained=state==0&&!rsp_valid;
 always @(posedge clk)begin
 if(rst)begin state<=0;rsp_valid<=0;data<=0;rsp_job<=0;error<=0;ram_addr<=0;size<=0;end
 else case(state)
 0:if(valid&&ready)begin ram_addr<=addr;rsp_job<=job;size<=bytes;state<=1;end
 1:state<=2;
 2:begin data<=size==1 ? ((ram_addr[19:16]>=4)?(ram_q>>(ram_addr[1:0]*8))&255:ram_q):ram_q;
 error<=!(size==1||size==4)||(size==4&&ram_addr[1:0]!=0);rsp_valid<=1;state<=3;end
 3:if(rsp_valid&&rsp_ready)begin rsp_valid<=0;state<=0;end
 endcase
 end
endmodule

// Stage admission has a separate edge before producer START; no overflow launch.
module stage5_control(input wire clk,rst,begin_load,start,loaded,session_valid,diagnostic,
 input wire resume,context_ok,reads_complete,abort_job,stage_done,drained,
 input wire [7:0] producer_error,
 output reg [2:0] stage,output reg [3:0] state,
 output wire conv_owner,post_owner,output reg conv_start,post_start,flush,
 output reg output_valid,output reg [7:0] error,
 output reg [31:0] job,token,output reg [63:0] network_starts,conv_starts,post_starts,compute_cycles,pause_cycles);
 localparam IDLE=0,LOAD=1,ADMIT=2,RUN=3,DRAIN=4,PAUSED=5,DONE=6,ERROR=7;
 reg diag;reg [63:0] pause_elapsed;
 assign conv_owner=(state==ADMIT||state==RUN||state==DRAIN)&&(stage==0||stage==2||stage==4);
 assign post_owner=(state==ADMIT||state==RUN||state==DRAIN)&&!(stage==0||stage==2||stage==4);
 task fatal(input [7:0] e);begin state<=ERROR;error<=e;output_valid<=0;flush<=1;conv_start<=0;post_start<=0;end endtask
 task advance;begin if(stage==7)begin state<=DONE;output_valid<=1;end else begin stage<=stage+1;state<=ADMIT;end end endtask
 always @(posedge clk)begin
 if(rst)begin stage<=0;state<=IDLE;conv_start<=0;post_start<=0;flush<=1;output_valid<=0;error<=0;job<=0;token<=0;network_starts<=0;conv_starts<=0;post_starts<=0;compute_cycles<=0;pause_cycles<=0;pause_elapsed<=0;diag<=0;end
 else begin
 conv_start<=0;post_start<=0;flush<=0;
 if(begin_load&&(state==IDLE||state==DONE||state==ERROR))begin state<=LOAD;output_valid<=0;error<=0;flush<=1;end
 if(start)begin
 if(state!=LOAD)error<=1;
 else if(!loaded||!session_valid)error<=6;
 else if(&network_starts||&job)fatal(7);
 else begin network_starts<=network_starts+1;job<=job+1;stage<=0;state<=ADMIT;output_valid<=0;compute_cycles<=0;pause_cycles<=0;diag<=diagnostic;error<=0;end
 end
 if(state==ADMIT)begin
 if(conv_owner)begin if(&conv_starts)fatal(7);else begin conv_starts<=conv_starts+1;conv_start<=1;state<=RUN;end end
 else begin if(&post_starts)fatal(7);else begin post_starts<=post_starts+1;post_start<=1;state<=RUN;end end
 end
 if(state==RUN)begin
 if(compute_cycles>=64'd5999999999)fatal(9);else compute_cycles<=compute_cycles+1;
 if(stage_done&&compute_cycles<64'd5999999999)state<=DRAIN;
 end
 if(state==DRAIN&&drained)begin
 if(diag)begin if(&token)fatal(7);else begin token<=token+1;state<=PAUSED;pause_elapsed<=0;end end
 else advance();
 end
 if(state==PAUSED)begin
 if(pause_elapsed>=64'd2999999999||&pause_cycles)fatal(9);
 else begin pause_elapsed<=pause_elapsed+1;pause_cycles<=pause_cycles+1;end
 if(resume&&pause_elapsed<64'd2999999999&&!(&pause_cycles))begin if(!context_ok)error<=10;else if(!reads_complete)error<=6;else advance();end
 end
 if((state==RUN||state==DRAIN)&&producer_error!=0)fatal(producer_error);
 if(abort_job)fatal(11);
 end
 end
endmodule

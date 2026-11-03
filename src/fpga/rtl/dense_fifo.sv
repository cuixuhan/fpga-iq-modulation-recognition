// 64 entries plus a synchronous read output register; occupancy includes it.
// No simultaneous read/write at the same address. Conservative refill bubble.
module dense_fifo(input wire clk, rst, input wire iv, output wire ir,
 input wire [63:0] id, output wire ov, input wire ory,
 output wire [63:0] od, output wire [6:0] occupancy);
 reg [5:0] wp,rp; reg [6:0] stored; reg valid;
 wire pop=valid && ory, push=iv&&ir;
 wire fetch=(!valid || pop) && stored!=0;
 assign occupancy=stored+valid;
 assign ir=occupancy<64;
 assign ov=valid;
 dense_ram #(.WIDTH(64),.DEPTH(64),.AW(6)) ram(
 .clk(clk),.we(push),.wa(wp),.wd(id),.re(fetch),.ra(rp),.q(od));
 always @(posedge clk) begin
  if(rst) begin wp<=0;rp<=0;stored<=0;valid<=0;end
  else begin
   case({push,fetch}) 2'b10:stored<=stored+1;2'b01:stored<=stored-1;default:;endcase
   if(push)wp<=wp+1;
   if(fetch)begin rp<=rp+1;valid<=1;end
   else if(pop)valid<=0;
  end
 end
endmodule

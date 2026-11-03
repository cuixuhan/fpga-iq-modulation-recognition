// Shared serial full signed32 * positive signed32 product. No DSP truncation.
module requant_even(input wire clk,rst, input wire iv, output wire ir,
 input wire signed [31:0] acc,m, input wire [31:0] shift,
 input wire signed [7:0] zy, input wire relu,
 output reg ov, input wire ory, output reg signed [7:0] data,
 output reg error);
 reg [2:0] state; reg [5:0] n,s; reg neg,rr;
 reg signed [7:0] z;
 reg [63:0] multiplicand,total; reg [31:0] multiplier;
 reg signed [63:0] product;
 wire [63:0] mask=(64'd1<<s)-1;
 wire [63:0] remainder=$unsigned(product)&mask;
 wire [63:0] half=64'd1<<(s-1);
 wire signed [63:0] quotient=product>>>s;
 wire up=(s!=0) && ((remainder>half)||((remainder==half)&&quotient[0]));
 wire signed [63:0] rounded=quotient+$signed({63'd0,up});
 wire signed [64:0] raw=$signed({rounded[63],rounded})+$signed({{57{z[7]}},z});
 wire signed [64:0] limited=(rr && raw<$signed(z)) ? $signed(z):raw;
 assign ir=state==0 && !ov;
 always @(posedge clk) begin
  if(rst) begin state<=0;ov<=0;error<=0;data<=0;total<=0;multiplicand<=0;multiplier<=0;product<=0;n<=0;s<=0;z<=0;rr<=0;neg<=0;end
  else begin
   if(ov&&ory)ov<=0;
   case(state)
    0:if(iv&&ir)begin
      error<=0;
      if(m<=0 || shift>62)begin error<=1;ov<=1;data<=0;end
      else begin
       multiplicand<=acc[31] ? -$signed({{32{acc[31]}},acc}) : {32'd0,acc};
       multiplier<=m;total<=0;neg<=acc[31];s<=shift[5:0];z<=zy;rr<=relu;n<=0;state<=1;
      end
    end
    1:begin
      if(multiplier[0])total<=total+multiplicand;
      multiplicand<=multiplicand<<1;multiplier<=multiplier>>1;
      if(n==31)state<=2;else n<=n+1;
    end
    2:begin product<=neg ? -$signed(total):$signed(total);state<=3;end
    3:begin
      error<=raw[64]!=raw[63];
      if(limited>127)data<=127;else if(limited< -128)data<=-128;else data<=limited[7:0];
      ov<=1;state<=0;
    end
   endcase
  end
 end
endmodule
